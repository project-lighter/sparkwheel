import ast
import warnings
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pprint import pformat
from pydoc import locate
from typing import Any

from .locations import LocationRegistry
from .path_utils import replace_references
from .utils import CompInitMode, first, instantiate, optional_import, run_debug, run_eval
from .utils.constants import EXPR_KEY, ID_SEP_KEY
from .utils.exceptions import EvaluationError, InstantiationError, Location, TargetNotFoundError
from .utils.module import describe_argument_error

__all__ = ["Item", "Expression", "Component", "Instantiable"]


class Instantiable(ABC):
    """
    Base class for an instantiable object.
    """

    @abstractmethod
    def is_disabled(self, *args: Any, **kwargs: Any) -> bool:
        """
        Return a boolean flag to indicate whether the object should be instantiated.
        """
        raise NotImplementedError(f"subclass {self.__class__.__name__} must implement this method.")

    @abstractmethod
    def instantiate(self, *args: Any, **kwargs: Any) -> object:
        """
        Instantiate the target component and return the instance.
        """
        raise NotImplementedError(f"subclass {self.__class__.__name__} must implement this method.")


class Item:
    """
    Basic data structure to represent a configuration item.

    A `Item` instance can optionally have a string id, so that other items can refer to it.
    It has a build-in `config` property to store the configuration object.

    Args:
        config: content of a config item, can be objects of any types,
            a configuration resolver may interpret the content to generate a configuration object.
        id: name of the current config item, defaults to empty string.
        source_location: optional location in source file where this config item was defined.
    """

    def __init__(self, config: Any, id: str = "", source_location: Location | None = None) -> None:
        self.config = config
        self.id = id
        self.source_location = source_location

    def get_id(self) -> str:
        """
        Get the ID name of current config item, useful to identify config items during parsing.
        """
        return self.id

    def update_config(self, config: Any) -> None:
        """
        Replace the content of `self.config` with new `config`.
        A typical usage is to modify the initial config content at runtime.

        Args:
            config: content of a `Item`.
        """
        self.config = config

    def get_config(self):
        """
        Get the config content of current config item.
        """
        return self.config

    def __repr__(self) -> str:
        return f"{type(self).__name__}: \n{pformat(self.config)}"


class Component(Item, Instantiable):
    """Component that can be instantiated from configuration.

    Uses a dictionary with string keys to represent a Python class or function
    that can be dynamically instantiated. Other keys are passed as arguments
    to the target component.

    Example:
        ```python
        from sparkwheel import Component

        # Basic instantiation with kwargs
        config = {
            "_target_": "collections.Counter",
            "iterable": [1, 2, 2, 3, 3, 3]
        }
        component = Component(config, id="counter")
        counter = component.instantiate()
        print(counter)  # Counter({3: 3, 2: 2, 1: 1})

        # With positional arguments using _args_
        config = {
            "_target_": "builtins.list",
            "_args_": [[1, 2, 3, 4, 5]]
        }
        component = Component(config, id="my_list")
        my_list = component.instantiate()
        print(my_list)  # [1, 2, 3, 4, 5]
        ```

    Args:
        config: Configuration content
        id: Identifier for this config item, defaults to ""
        source_location: Location where this component was defined
        locations: Registry with the locations of the component's keys, so errors can
            point at the `_target_` or argument that caused them

    Note:
        Special configuration keys:

        - `_target_`: Full module path (e.g., "collections.Counter")
        - `_args_`: List of positional arguments to pass to the target
        - `_disabled_`: Skip instantiation if True
        - `_mode_`: Instantiation mode:
            - `"default"`: Returns component(*args, **kwargs)
            - `"callable"`: Returns functools.partial(component, *args, **kwargs)
            - `"debug"`: Returns pdb.runcall(component, *args, **kwargs)
    """

    non_arg_keys = {"_target_", "_disabled_", "_mode_", "_args_"}

    def __init__(
        self,
        config: Any,
        id: str = "",
        source_location: Location | None = None,
        locations: LocationRegistry | None = None,
    ) -> None:
        super().__init__(config=config, id=id, source_location=source_location)
        self.locations = locations

    def location_of(self, key: str) -> Location | None:
        """Location of one of this component's keys, or of the component itself if unknown."""
        location = self.locations.get(f"{self.id}{ID_SEP_KEY}{key}" if self.id else key) if self.locations else None
        return location or self.source_location

    @staticmethod
    def is_instantiable(config: Any) -> bool:
        """
        Check whether this config represents a `class` or `function` that is to be instantiated.

        Args:
            config: input config content to check.
        """
        return isinstance(config, Mapping) and "_target_" in config

    def resolve_module_name(self):
        """Resolve the target module name from configuration.

        Requires full module path (e.g., "collections.Counter").
        No automatic module discovery is performed.

        Returns:
            str or callable: The module path or callable from _target_
        """
        config = dict(self.get_config())
        target = config.get("_target_")
        if not isinstance(target, str):
            return target  # for cases where _target_ is already a callable

        # No ComponentLocator - just return the target as-is (must be full path)
        return target

    def resolve_args(self):
        """
        Utility function used in `instantiate()` to resolve the arguments from current config content.

        Returns:
            tuple: A tuple of (args, kwargs) where:
                - args is a list of positional arguments from _args_ (or empty list if not present)
                - kwargs is a dict of keyword arguments (excluding special keys)
        """
        config = self.get_config()
        if not isinstance(config, Mapping):
            raise TypeError(
                f"Expected config to be a Mapping (dict-like), but got {type(config).__name__}. "
                f"Cannot resolve arguments from non-mapping config."
            )

        # Extract positional args from _args_ if present
        args = config.get("_args_", [])
        if not isinstance(args, list):
            raise TypeError(
                f"Expected _args_ to be a list, but got {type(args).__name__}. _args_ must be a list of positional arguments."
            )

        # Extract keyword arguments (excluding special keys)
        kwargs = {k: v for k, v in config.items() if k not in self.non_arg_keys}

        return args, kwargs

    def is_disabled(self) -> bool:
        """
        Utility function used in `instantiate()` to check whether to skip the instantiation.
        """
        _is_disabled = self.get_config().get("_disabled_", False)
        return _is_disabled.lower().strip() == "true" if isinstance(_is_disabled, str) else bool(_is_disabled)

    def instantiate(self, **kwargs: Any) -> object:
        """
        Instantiate component based on ``self.config`` content.
        The target component must be a `class` or a `function`, otherwise, return `None`.

        Args:
            kwargs: args to override / add the config args when instantiation.
        """
        if not self.is_instantiable(self.get_config()) or self.is_disabled():
            # if not a class or function or marked as `disabled`, skip parsing and return `None`
            return None

        modname = self.resolve_module_name()
        mode = self.get_config().get("_mode_", CompInitMode.DEFAULT)
        args, config_kwargs = self.resolve_args()
        config_kwargs.update(kwargs)

        try:
            return instantiate(modname, mode, *args, **config_kwargs)
        except TargetNotFoundError as e:
            # Re-raise with source location and suggestions
            suggestion = self._suggest_similar_modules(modname) if isinstance(modname, str) else None
            raise TargetNotFoundError(
                f"Cannot locate class or function: '{modname}'",
                source_location=self.location_of("_target_"),
                suggestion=suggestion,
            ) from e
        except InstantiationError as e:
            if isinstance(e.__cause__, TypeError):
                # Wrong argument names point at the argument; a TypeError raised inside the target is kept as is
                target = locate(modname) if isinstance(modname, str) else modname
                errors = self.argument_errors(target, args, config_kwargs, allow_missing=mode == "callable")
                if errors:
                    raise errors[0] from e.__cause__
            # Add source location if not already present, preserving original message and suggestion
            if e.source_location is None:
                raise InstantiationError(
                    e._original_message, source_location=self.source_location, suggestion=e.suggestion
                ) from (e.__cause__ or e)
            raise  # Already has location, re-raise as-is
        except Exception as e:
            # Wrap unexpected errors with component context and location
            raise InstantiationError(
                f"Failed to instantiate '{modname}': {type(e).__name__}: {e}",
                source_location=self.source_location,
            ) from e

    def argument_errors(
        self, target: Any, args: list[Any], kwargs: dict[str, Any], allow_missing: bool = False
    ) -> list[InstantiationError]:
        """The errors for arguments that do not fit `target`'s signature: one per unknown argument, each pointing
        at it, or else the other mismatch (such as a missing argument)."""
        errors: list[InstantiationError] = []
        kwargs = dict(kwargs)
        while (problem := describe_argument_error(target, args, kwargs, allow_missing=allow_missing)) is not None:
            message, suggestion, key = problem
            if key is None and errors:
                break  # a missing argument is most likely the misspelled one already reported
            location = self.location_of(key) if key else self.source_location
            errors.append(InstantiationError(f"'{self.resolve_module_name()}' {message}", location, suggestion))
            if key is None:
                break
            del kwargs[key]
        return errors

    def _suggest_similar_modules(self, target: str) -> str | None:
        """Suggest similar valid module names using fuzzy matching.

        Args:
            target: The module path that couldn't be found (e.g., 'torch.optim.Adamfad')

        Returns:
            A helpful suggestion string, or None if no good suggestions found.
        """
        if not isinstance(target, str) or "." not in target:
            return None

        try:
            from .utils import damerau_levenshtein_distance

            # Split into module path and attribute name
            parts = target.rsplit(".", 1)
            base_module, attr_name = parts[0], parts[1]

            # Try to import the base module
            base = locate(base_module)
            if base is None:
                parts = target.split(".")
                missing = next(".".join(parts[:i]) for i in range(1, len(parts)) if locate(".".join(parts[:i])) is None)
                return f"'{missing}' cannot be imported: check its spelling and that it is installed or on sys.path."

            # Find similar attribute names in the module
            similar = []
            for name in dir(base):
                if name.startswith("_"):
                    continue
                distance = damerau_levenshtein_distance(name, attr_name)
                if distance <= 2:  # Allow up to 2 character edits
                    similar.append((distance, name))

            if similar:
                # Sort by distance and return the closest match
                similar.sort(key=lambda x: x[0])
                closest = similar[0][1]
                return f"Did you mean '{base_module}.{closest}'?"
        except Exception:
            # If anything fails during suggestion generation, just skip it
            pass

        return None


class Expression(Item):
    """Executable expression that evaluates Python code.

    Expressions start with `$` and are evaluated using Python's `eval()`,
    or imported if they're import statements.

    Example:
        ```python
        from sparkwheel import Expression

        config = "$len([1, 2, 3])"
        expression = Expression(config, id="test", globals={"len": len})
        print(expression.evaluate())  # 3
        ```

    Args:
        config: Expression string starting with `$`
        id: Identifier for this config item, defaults to ""
        globals: Additional global context for evaluation

    See Also:
        [Python eval documentation](https://docs.python.org/3/library/functions.html#eval)
    """

    prefix = EXPR_KEY
    run_eval = run_eval
    refs_var = "__local_refs"  # global holding resolved `@` references during evaluation

    def __init__(
        self,
        config: Any,
        id: str = "",
        globals: dict[str, Any] | None = None,
        source_location: Location | None = None,
    ) -> None:
        super().__init__(config=config, id=id, source_location=source_location)
        self.globals = globals if globals is not None else {}

    def _parse_import_string(self, import_string: str) -> Any | None:
        """parse single import statement such as "from pathlib import Path" """
        node = first(ast.iter_child_nodes(ast.parse(import_string)))
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            return None
        if len(node.names) < 1:
            return None
        if len(node.names) > 1:
            warnings.warn(f"ignoring multiple import alias '{import_string}'.", stacklevel=2)
        name, asname = f"{node.names[0].name}", node.names[0].asname
        asname = name if asname is None else f"{asname}"
        if isinstance(node, ast.ImportFrom):
            self.globals[asname], _ = optional_import(f"{node.module}", name=f"{name}")
            return self.globals[asname]
        if isinstance(node, ast.Import):
            self.globals[asname], _ = optional_import(f"{name}")
            return self.globals[asname]
        return None  # type: ignore[unreachable]

    def evaluate(self, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None) -> str | Any | None:
        """Evaluate the expression and return the result.

        Uses Python's `eval()` to execute the expression string. `@id` references are looked up
        in the resolved references passed as the `__local_refs` global.

        Args:
            globals: Additional global symbols for evaluation
            locals: Additional local symbols for evaluation

        Returns:
            Evaluation result, or None if not an expression

        Raises:
            EvaluationError: If parsing or evaluation fails. The message names the Python error
                and shows the expression as written.
        """
        value = self.get_config()
        if not Expression.is_expression(value):
            return None
        globals_ = dict(self.globals)
        if globals is not None:
            for k, v in globals.items():
                if k in globals_:
                    warnings.warn(f"the new global variable `{k}` conflicts with `self.globals`, override it.", stacklevel=2)
                globals_[k] = v
        try:
            code = replace_references(value, globals_.get(self.refs_var, {}), self.refs_var)[len(self.prefix) :]
            optional_module = self._parse_import_string(code)
            if optional_module is not None:
                return optional_module
            if not self.run_eval:
                return f"{value[len(self.prefix) :]}"
            if not run_debug:
                return eval(code, globals_, locals)
        except Exception as e:
            raise self._evaluation_error(e) from e
        warnings.warn(
            f"\n\npdb: value={value}\nSee also Debugger commands documentation: https://docs.python.org/3/library/pdb.html\n",
            stacklevel=2,
        )
        import pdb  # noqa: T100

        pdb.run(code, globals_, locals)
        return None

    def _evaluation_error(self, error: Exception) -> EvaluationError:
        """Describe a failed expression with the Python error and the expression as written."""
        detail = error.msg if isinstance(error, SyntaxError) else str(error)
        suggestion = None
        name = getattr(error, "name", None)
        if isinstance(error, NameError) and name:
            suggestion = (
                f"To use the module `{name}`, import it in the config (`_imports_: {{{name}: {name}}}`); "
                f"for the config value `{name}`, write `@{name}`."
            )
        return EvaluationError(
            f"Failed to evaluate expression '{self.get_config()}': {type(error).__name__}: {detail}",
            source_location=self.source_location,
            suggestion=suggestion,
        )

    @classmethod
    def is_expression(cls, config: dict[str, Any] | list[Any] | str) -> bool:
        """
        Check whether the config is an executable expression string.
        Currently, a string starts with ``"$"`` character is interpreted as an expression.

        Args:
            config: input config content to check.
        """
        return isinstance(config, str) and config.startswith(cls.prefix)

    @classmethod
    def is_import_statement(cls, config: dict[str, Any] | list[Any] | str) -> bool:
        """
        Check whether the config is an import statement (a special case of expression).

        Args:
            config: input config content to check.
        """
        if not cls.is_expression(config):
            return False
        if "import" not in config:
            return False
        try:
            tree = ast.parse(f"{config[len(cls.prefix) :]}")  # type: ignore[index]
        except SyntaxError:
            return False  # e.g. `$@a['import']`; evaluating it reports any real syntax error
        return isinstance(first(ast.iter_child_nodes(tree)), (ast.Import, ast.ImportFrom))
