"""Retained definitions and isolated resolution scopes for framework integrations."""

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .config import Config
from .items import Component, Expression
from .operators import _copy_containers
from .parser import Parser
from .path_utils import get_by_id, resolve_relative_ids, split_file_and_id, split_id
from .resolver import Resolver
from .utils.exceptions import CircularReferenceError, ConfigKeyError


def _within(path: str, parent: str) -> bool:
    return path == parent or not parent or path.startswith(parent + "::")


def _child(parent: str, key: Any) -> str:
    return f"{parent}::{key}" if parent else str(key)


@dataclass(frozen=True)
class _Boundary:
    """Internal placeholder that dependency scanning can see without traversing."""

    path: str


class RetainedConfig:
    """A container snapshot without runtime caches; obtain through Config.retain()."""

    def __init__(self, config: Config):
        self._source = _copy_containers(config.get())
        self._imports = dict(config._provided_imports)
        self._locations = deepcopy(config._locations)

    def definition(self, path: str = "") -> Any:
        """Inspect one retained definition without running configured Python.

        Follow only local raw-copy chains needed to select the node. References
        and expressions inside the returned container remain authored strings.
        Containers are detached; opaque Python leaves retain their identity.
        """
        if not isinstance(path, str):
            raise TypeError("Definition paths must be strings")
        try:
            value, origin = self._definition(path)
            value, _ = self._unwrap(value, origin, frozenset())
        except (KeyError, TypeError, IndexError) as error:
            raise ConfigKeyError(f"Unknown definition path '{path}'", missing_key=path) from error
        return _copy_containers(value)

    def scope(
        self,
        *,
        bindings: dict[str, Any] | None = None,
        blocked_paths: set[str] | None = None,
    ) -> "ResolutionScope":
        """Create a fresh scope without executing configured imports or targets."""
        return ResolutionScope(self, bindings or {}, blocked_paths or set())

    def _definition(self, path: str, seen: frozenset[str] = frozenset()) -> tuple[Any, str]:
        """Find a source path, following local copies without executing Python."""
        node = self._source
        origin = ""
        for key in split_id(path) if path else []:
            node, origin = self._unwrap(node, origin, seen)
            if isinstance(node, list) and (not key.isdigit() or str(int(key)) != key):
                raise KeyError(f"Construction list index '{key}' must be a non-negative canonical index")
            node = get_by_id(node, key)
            origin = _child(origin, key)
        return node, origin

    def _unwrap(self, value: Any, origin: str, seen: frozenset[str]) -> tuple[Any, str]:
        while isinstance(value, str) and value.startswith("%"):
            reference = resolve_relative_ids(origin, value)
            if reference in seen:
                raise CircularReferenceError(f"Circular raw reference at '{origin}': {reference}")
            seen = seen | {reference}
            file, path = split_file_and_id(reference[1:])
            if file:
                raise ValueError("Load external includes with Config.update() before retaining their descendant paths")
            value, origin = self._definition(path, seen)
        return value, origin


class ResolutionScope:
    """One runtime graph with exact bindings and explicit forbidden source paths."""

    def __init__(self, recipe: RetainedConfig, bindings: dict[str, Any], blocked_paths: set[str]):
        self._recipe = recipe
        self._bindings: dict[str, Any] = {}
        self._blocked = set(blocked_paths)
        self._consumed: dict[str, Any] = {}
        self._components: dict[str, Any] = {}
        self._active_paths: set[str] = set()
        self._config = Config()
        self._config._imports = dict(recipe._imports)
        self._imports_loaded = False
        self._resolver = _ScopedResolver(self)
        for path in self._blocked:
            self._validate_path(path)
        for path, value in bindings.items():
            self.bind(path, value)

    def _validate_path(self, path: str) -> None:
        if not isinstance(path, str):
            raise TypeError("Construction paths must be strings")
        try:
            self._recipe._definition(path)
        except (KeyError, TypeError, IndexError) as error:
            raise ConfigKeyError(f"Unknown construction path '{path}'", missing_key=path) from error
        if path == "_imports_" or path.startswith("_imports_::"):
            raise ValueError("Import declarations are not runtime binding paths")

    def _check_block(self, path: str) -> None:
        for blocked in self._blocked:
            if _within(path, blocked):
                raise ValueError(f"Cannot resolve '{path}': construction path '{blocked}' is blocked")

    def bind(self, path: str, value: Any) -> None:
        """Bind a valid exact source path, rejecting incompatible prior use."""
        self._validate_path(path)
        self._check_block(path)
        for values in (self._bindings, self._resolver._resolved, self._consumed):
            if path in values:
                if values[path] is not value:
                    raise ValueError(f"Cannot rebind '{path}' to a different identity after use; create a fresh scope")
                break
        self._bindings[path] = value
        self._resolver._resolved[path] = value
        # Existing compiled ancestors may contain this path. Substitution observes
        # bindings directly; already consumed ancestors were checked above.

    def resolve(self, path: str = "") -> Any:
        """Resolve a source path after checking explicit dependency boundaries."""
        self._validate_path(path)
        self._active_paths = set()
        self._preflight(path, set())
        if path in self._resolver._resolved:
            return self._resolver._resolved[path]
        if not self._imports_loaded:
            self._load_imports()
            self._imports_loaded = True
        return self._resolver.resolve(path)

    def materialized_components(self) -> dict[str, Any]:
        """Return constructed _target_ identities, excluding bindings/expressions."""
        return dict(self._components)

    def _preflight(self, path: str, visiting: set[str]) -> None:
        self._check_block(path)
        self._active_paths.add(path)
        if path in self._bindings or path in self._resolver._resolved:
            return
        if path in visiting:
            raise CircularReferenceError(f"Circular reference while resolving '{path}'")
        self._resolver._prepare_item(path)
        visiting.add(path)
        item = self._resolver._items[path]
        for dependency in self._resolver.find_refs_in_config(item.get_config(), path):
            self._preflight(dependency, visiting)
        visiting.remove(path)

    def _compile(self, value: Any, path: str, origin: str, seen: frozenset[str] = frozenset()) -> Any:
        if path in self._bindings or any(_within(path, blocked) for blocked in self._blocked):
            # Represent boundaries as pure references; normal Resolver scans and
            # substitution then preserve the boundary without walking inside it.
            return _Boundary(path)
        if isinstance(value, str) and value.startswith("%"):
            reference = resolve_relative_ids(origin, value)
            if reference in seen:
                raise CircularReferenceError(f"Circular raw reference at '{path}': {reference}")
            file, target = split_file_and_id(reference[1:])
            if file:
                # Config.update freezes external includes before retain. Do not
                # silently turn an unexpanded include into a later file read.
                raise ValueError("Load external includes with Config.update() before retaining")
            copied, copied_origin = self._recipe._definition(target)
            return self._compile(copied, path, copied_origin, seen | {reference})
        if isinstance(value, dict):
            return {
                key: self._compile(item, _child(path, key), _child(origin, key), seen)
                for key, item in value.items()
                if path or key != "_imports_"
            }
        if isinstance(value, list):
            return [self._compile(item, _child(path, i), _child(origin, i), seen) for i, item in enumerate(value)]
        return resolve_relative_ids(path, value) if isinstance(value, str) else value

    def _load_imports(self) -> None:
        declaration = self._recipe._source.get("_imports_")
        self._config._process_imports_key({"_imports_": declaration})

        def collect(value: Any, path: str) -> None:
            if path in self._bindings or any(_within(path, blocked) for blocked in self._blocked):
                return
            if isinstance(value, dict):
                for key, child in value.items():
                    if path or key != "_imports_":
                        collect(child, _child(path, key))
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    collect(child, _child(path, i))
            elif isinstance(value, str) and Expression.is_import_statement(value):
                self._resolver._prepare_item(path)

        collect(self._recipe._source, "")


class _ScopedResolver(Resolver):
    def __init__(self, scope: ResolutionScope):
        super().__init__()
        self._scope = scope

    def _prepare_item(self, id: str) -> None:
        if id in self._items:
            return
        self._scope._validate_path(id)
        value, origin = self._scope._recipe._definition(id)
        compiled = self._scope._compile(value, id, origin)
        # Boundaries must be dependencies even when their source is a scalar.
        compiled = self._reference_boundaries(compiled)
        parser = Parser(globals=self._scope._config._imports, metadata=self._scope._recipe._locations)
        for item in parser.parse(compiled, id_prefix=id):
            if item.get_id() not in self._items:
                self.add_item(item)

    @classmethod
    def _reference_boundaries(cls, value: Any) -> Any:
        if isinstance(value, _Boundary):
            return "@" + value.path
        if isinstance(value, dict):
            return {key: cls._reference_boundaries(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._reference_boundaries(item) for item in value]
        return value

    def _resolve_imports(self, resolved: dict[str, Any], eval_expr: bool) -> None:
        for id, item in self._items.items():
            if any(_within(id, parent) for parent in self._scope._blocked) or id in self._scope._bindings:
                continue
            if id not in self._scope._active_paths and any(_within(id, parent) for parent in self._scope._bindings):
                continue
            if id not in resolved and isinstance(item, Expression) and item.is_import_statement(item.get_config()):
                resolved[id] = item.evaluate() if eval_expr else item

    def _substitute_refs(self, config: Any, id: str, refs: dict[str, Any]) -> Any:
        if id in self._scope._bindings:
            result = self._scope._bindings[id]
        elif isinstance(config, (dict, list)):
            result = type(config)()
            for key, path, value in self.iter_subconfigs(id, config):
                if path in self._scope._bindings:
                    resolved = self._scope._bindings[path]
                elif Component.is_instantiable(value) or Expression.is_expression(value):
                    resolved = refs[path]
                    if Component.is_instantiable(value) and resolved is None:
                        continue
                else:
                    resolved = self._substitute_refs(value, path, refs)
                self._scope._consumed[path] = resolved
                if isinstance(result, dict):
                    result[key] = resolved
                else:
                    result.append(resolved)
        else:
            result = self.update_config_with_refs(config, id, refs)
        self._scope._consumed[id] = result
        return result

    def _resolve_one_item(
        self,
        id: str,
        waiting_list: set[str] | None = None,
        _depth: int = 0,
        instantiate: bool = True,
        eval_expr: bool = True,
        default: Any = None,
    ) -> Any:
        cached = id in self._resolved
        result = super()._resolve_one_item(
            id, waiting_list=waiting_list, _depth=_depth, instantiate=instantiate, eval_expr=eval_expr, default=default
        )
        if (
            not cached
            and id not in self._scope._bindings
            and isinstance(self._items.get(id), Component)
            and result is not None
            and not isinstance(result, Iterator)
        ):
            self._scope._components[id] = result
        return result
