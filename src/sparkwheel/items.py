import ast
import warnings
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pprint import pformat
from typing import Any

from .utils import CompInitMode, first, instantiate, optional_import, run_debug, run_eval
from .utils.constants import EXPR_KEY
from .utils.exceptions import EvaluationError, InstantiationError, ModuleNotFoundError, SourceLocation

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

    def __init__(self, config: Any, id: str = "", source_location: SourceLocation | None = None) -> None:
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
        from sparkwheel import ConfigComponent
        from collections import Counter

        config = {
            "_target_": "collections.Counter",
            "iterable": [1, 2, 2, 3, 3, 3]
        }

        component = ConfigComponent(config, id="counter")
        counter = component.instantiate()
        print(counter)  # Counter({3: 3, 2: 2, 1: 1})
        ```

    Args:
        config: Configuration content
        id: Identifier for this config item, defaults to ""

    Note:
        Special configuration keys:

        - `_target_`: Full module path (e.g., "collections.Counter")
        - `_requires_`: Dependencies to evaluate/instantiate first
        - `_disabled_`: Skip instantiation if True
        - `_mode_`: Instantiation mode:
            - `"default"`: Returns component(**kwargs)
            - `"callable"`: Returns functools.partial(component, **kwargs)
            - `"debug"`: Returns pdb.runcall(component, **kwargs)
    """

    non_arg_keys = {"_target_", "_disabled_", "_requires_", "_mode_"}

    def __init__(self, config: Any, id: str = "", source_location: SourceLocation | None = None) -> None:
        super().__init__(config=config, id=id, source_location=source_location)

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
        """
        config = self.get_config()
        if not isinstance(config, Mapping):
            raise TypeError(
                f"Expected config to be a Mapping (dict-like), but got {type(config).__name__}. "
                f"Cannot resolve arguments from non-mapping config."
            )
        return {k: v for k, v in config.items() if k not in self.non_arg_keys}

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
        args = self.resolve_args()
        args.update(kwargs)

        try:
            return instantiate(modname, mode, **args)
        except ModuleNotFoundError as e:
            # Re-raise with source location and suggestions
            suggestion = self._suggest_similar_modules(modname) if isinstance(modname, str) else None
            raise ModuleNotFoundError(
                f"Cannot locate class or function: '{modname}'",
                source_location=self.source_location,
                suggestion=suggestion,
            ) from e
        except Exception as e:
            # Wrap other errors with location context (points to _target_ line)
            raise InstantiationError(
                f"Failed to instantiate '{modname}': {type(e).__name__}: {e}",
                source_location=self.source_location,
            ) from e

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
            from pydoc import locate

            from .utils import damerau_levenshtein_distance

            # Split into module path and attribute name
            parts = target.rsplit(".", 1)
            base_module, attr_name = parts[0], parts[1]

            # Try to import the base module
            base = locate(base_module)
            if base is None:
                return None

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
        from sparkwheel import ConfigExpression

        config = "$len([1, 2, 3])"
        expression = ConfigExpression(config, id="test", globals={"len": len})
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

    def __init__(
        self,
        config: Any,
        id: str = "",
        globals: dict | None = None,
        source_location: SourceLocation | None = None,
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
        return None

    def evaluate(self, globals: dict | None = None, locals: dict | None = None) -> str | Any | None:
        """Evaluate the expression and return the result.

        Uses Python's `eval()` to execute the expression string.

        Args:
            globals: Additional global symbols for evaluation
            locals: Additional local symbols for evaluation

        Returns:
            Evaluation result, or None if not an expression

        Raises:
            RuntimeError: If evaluation fails
        """
        value = self.get_config()
        if not Expression.is_expression(value):
            return None
        optional_module = self._parse_import_string(value[len(self.prefix) :])
        if optional_module is not None:
            return optional_module
        if not self.run_eval:
            return f"{value[len(self.prefix) :]}"
        globals_ = dict(self.globals)
        if globals is not None:
            for k, v in globals.items():
                if k in globals_:
                    warnings.warn(f"the new global variable `{k}` conflicts with `self.globals`, override it.", stacklevel=2)
                globals_[k] = v
        if not run_debug:
            try:
                return eval(value[len(self.prefix) :], globals_, locals)
            except Exception as e:
                raise EvaluationError(
                    f"Failed to evaluate expression: '{value[len(self.prefix) :]}'",
                    source_location=self.source_location,
                ) from e
        warnings.warn(
            f"\n\npdb: value={value}\nSee also Debugger commands documentation: https://docs.python.org/3/library/pdb.html\n",
            stacklevel=2,
        )
        import pdb

        pdb.run(value[len(self.prefix) :], globals_, locals)
        return None

    @classmethod
    def is_expression(cls, config: dict | list | str) -> bool:
        """
        Check whether the config is an executable expression string.
        Currently, a string starts with ``"$"`` character is interpreted as an expression.

        Args:
            config: input config content to check.
        """
        return isinstance(config, str) and config.startswith(cls.prefix)

    @classmethod
    def is_import_statement(cls, config: dict | list | str) -> bool:
        """
        Check whether the config is an import statement (a special case of expression).

        Args:
            config: input config content to check.
        """
        if not cls.is_expression(config):
            return False
        if "import" not in config:
            return False
        return isinstance(first(ast.iter_child_nodes(ast.parse(f"{config[len(cls.prefix) :]}"))), (ast.Import, ast.ImportFrom))
