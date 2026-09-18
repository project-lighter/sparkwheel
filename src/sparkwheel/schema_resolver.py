"""Schema checks on resolved argument trees, before component construction."""

import dataclasses
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from .items import Component, Expression
from .resolver import Resolver
from .schema import (
    _coerce_field,
    _find_discriminator,
    _is_union_type,
    _schema_hints,
    _validate_field,
)
from .utils.exceptions import CircularReferenceError

if TYPE_CHECKING:
    from .config import Config


class _SchemaResolver(Resolver):
    """Keep validation projections separate from live runtime objects.

    A component's projection is its resolved constructor-argument mapping. Its
    runtime cache still contains the native object passed to other constructors.
    Only requested nodes, their ordinary dependencies, and schema discriminator
    dependencies needed to select a variant are resolved.
    """

    def __init__(self, config: "Config"):
        super().__init__()
        self._config = config
        self._projections: dict[tuple[bool, bool], dict[str, Any]] = {}
        self._mode = (True, True)

    def reset(self) -> None:
        super().reset()
        self._projections = {}

    def _annotation(self, path: str) -> Any:
        annotation = self._config._schema
        parent = ""
        for key in path.split("::") if path else []:
            item = self._items.get(parent)
            source = item.get_config() if item is not None else None
            if isinstance(source, dict):
                cache = self._resolved_by_mode[self._mode]
                source = {name: cache.get(f"{parent}::{name}" if parent else name, value) for name, value in source.items()}
            annotation = self._child_annotation(annotation, key, source)
            parent = f"{parent}::{key}" if parent else key
        return annotation

    def _child_annotation(self, annotation: Any, key: str, source: Any) -> Any:
        origin, args = get_origin(annotation), get_args(annotation)
        if _is_union_type(origin):
            branches = [branch for branch in args if branch is not type(None)]
            _, discriminator = _find_discriminator(tuple(branches))
            if discriminator and isinstance(source, dict):
                chosen = source.get(discriminator)
                matching = [
                    branch
                    for branch in branches
                    if isinstance(branch, type)
                    and dataclasses.is_dataclass(branch)
                    and chosen in get_args(_schema_hints(branch).get(discriminator))
                ]
                if matching:
                    branches = matching
            children = [self._child_annotation(branch, key, source) for branch in branches]
            if not children or Any in children:
                return Any
            return children[0] if all(child == children[0] for child in children) else Union[tuple(children)]
        if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
            return _schema_hints(annotation).get(key, Any)
        if origin is list and args:
            return args[0]
        if origin is dict and len(args) == 2:
            return args[1]
        return Any

    def _prepare_discriminators(self, path: str, waiting: set[str], depth: int) -> None:
        """Resolve only discriminator dependencies needed to type this path."""
        parts = path.split("::") if path else []
        for length in range(len(parts) + 1):
            parent = "::".join(parts[:length])
            annotation = self._annotation(parent)
            if not _is_union_type(get_origin(annotation)):
                continue
            _, discriminator = _find_discriminator(get_args(annotation))
            item = self._items.get(parent)
            source = item.get_config() if item is not None else None
            if not discriminator or not isinstance(source, dict):
                continue
            raw = source.get(discriminator)
            if not isinstance(raw, str) or not raw.startswith(("@", "$")):
                continue
            dependency = f"{parent}::{discriminator}" if parent else discriminator
            if dependency == path or dependency in self._projections.get(self._mode, {}):
                continue
            if dependency in waiting:
                raise CircularReferenceError(f"Circular schema discriminator dependency at '{dependency}'")
            self._resolve_one_item(dependency, waiting | {path}, depth + 1, instantiate=self._mode[0], eval_expr=self._mode[1])

    def _normalize(self, value: Any, annotation: Any, path: str) -> Any:
        if self._config._coerce:
            # Constructor arguments already used to create native objects cannot
            # be re-coerced through a differently annotated alias or ancestor.
            cache = self._resolved_by_mode[self._mode]
            projections = self._projections.setdefault(self._mode, {})
            preserve = {
                identity
                for key, item in self._items.items()
                if key in cache
                and key in projections
                and (isinstance(item, Component) or isinstance(cache[key], (dict, list)))
                for identity in (id(cache[key]), id(projections.get(key)))
            }
            return _coerce_field(
                value,
                annotation,
                path.replace("::", "."),
                self._config._locations,
                strict=self._config._strict,
                allow_missing=self._config._allow_missing,
                allow_unresolved=False,
                _preserve=preserve,
            )
        return value

    def _check(self, value: Any, annotation: Any, path: str) -> Any:
        normalized = self._normalize(value, annotation, path)
        _validate_field(
            normalized,
            annotation,
            path.replace("::", "."),
            self._config._locations,
            strict=self._config._strict,
            allow_missing=self._config._allow_missing,
            allow_unresolved=False,
        )
        return normalized

    def _substitute_cached(self, config: Any, path: str, refs: dict[str, Any], *, root: bool = True) -> Any:
        if not root and path in refs:
            return refs[path]
        if not isinstance(config, (dict, list)):
            return self.update_config_with_refs(config, path, refs)
        result: Any = type(config)()
        for key, child_path, child in self.iter_subconfigs(path, config):
            value = self._substitute_cached(child, child_path, refs, root=False)
            if Component.is_instantiable(child) and value is None:
                continue
            if isinstance(result, dict):
                result[key] = value
            else:
                result.append(value)
        return result

    def _substitute_refs(self, config: Any, id: str, refs: dict[str, Any]) -> Any:
        actual = self._substitute_cached(config, id, refs)
        if not self._mode[1] or isinstance(self._items[id], Expression):
            return actual
        projections = self._projections.setdefault(self._mode, {})
        projected_refs = {key: projections.get(key, value) for key, value in refs.items()}
        projected = self._substitute_cached(config, id, projected_refs)
        annotation = self._annotation(id)
        projections[id] = self._check(projected, annotation, id)
        return self._normalize(actual, annotation, id)

    def _resolve_one_item(
        self,
        id: str,
        waiting_list: set[str] | None = None,
        _depth: int = 0,
        instantiate: bool = True,
        eval_expr: bool = True,
        default: Any = None,
    ) -> Any:
        id = self.normalize_id(id)
        self._mode = (instantiate, eval_expr)
        cache = self._resolved_by_mode.setdefault(self._mode, {})
        if eval_expr and id in self._items and _depth < self.max_resolution_depth:
            self._prepare_discriminators(id, waiting_list or set(), _depth)
        result = super()._resolve_one_item(id, waiting_list, _depth, instantiate, eval_expr, default)
        if eval_expr and isinstance(self._items.get(id), Expression) and id not in self._projections.get(self._mode, {}):
            try:
                result = self._check(result, self._annotation(id), id)
            except Exception:
                cache.pop(id, None)
                raise
            cache[id] = result
            self._projections.setdefault(self._mode, {})[id] = result
        return result
