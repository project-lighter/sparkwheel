import enum
import os
import pdb
import warnings
from collections.abc import Collection, Hashable
from functools import partial
from importlib import import_module
from pydoc import locate
from typing import Any

from sparkwheel.utils.enums import CompInitMode
from sparkwheel.utils.exceptions import InstantiationError, ModuleNotFoundError

__all__ = [
    "run_eval",
    "run_debug",
    "allow_missing_reference",
    "damerau_levenshtein_distance",
    "look_up_option",
    "optional_import",
    "instantiate",
]

# Configuration system flags (environment variables)
# set SPARKWHEEL_EVAL_EXPR=0 to disable 'eval', default: True
run_eval = os.environ.get("SPARKWHEEL_EVAL_EXPR", "1") != "0"
# set SPARKWHEEL_DEBUG=1 to run in debug mode, default: False
run_debug = os.environ.get("SPARKWHEEL_DEBUG", "0") != "0"
# set SPARKWHEEL_ALLOW_MISSING_REF=1 to allow missing references, default: False
allow_missing_reference = os.environ.get("SPARKWHEEL_ALLOW_MISSING_REF", "0") != "0"


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates the Damerau–Levenshtein distance between two strings for spelling correction.
    https://en.wikipedia.org/wiki/Damerau–Levenshtein_distance
    """
    if s1 == s2:
        return 0
    string_1_length = len(s1)
    string_2_length = len(s2)
    if not s1:
        return string_2_length
    if not s2:
        return string_1_length
    d = {(i, -1): i + 1 for i in range(-1, string_1_length + 1)}
    for j in range(-1, string_2_length + 1):
        d[(-1, j)] = j + 1

    for i, s1i in enumerate(s1):
        for j, s2j in enumerate(s2):
            cost = 0 if s1i == s2j else 1
            d[(i, j)] = min(
                d[(i - 1, j)] + 1,  # deletion
                d[(i, j - 1)] + 1,  # insertion
                d[(i - 1, j - 1)] + cost,  # substitution
            )
            if i and j and s1i == s2[j - 1] and s1[i - 1] == s2j:
                d[(i, j)] = min(d[(i, j)], d[i - 2, j - 2] + cost)  # transposition

    return d[string_1_length - 1, string_2_length - 1]


def look_up_option(
    opt_str: Hashable,
    supported: Collection | enum.EnumMeta,
    default: Any = "no_default",
    print_all_options: bool = True,
) -> Any:
    """
    Look up the option in the supported collection and return the matched item.
    Raise a value error possibly with a guess of the closest match.

    Args:
        opt_str: The option string or Enum to look up.
        supported: The collection of supported options, it can be list, tuple, set, dict, or Enum.
        default: If it is given, this method will return `default` when `opt_str` is not found,
            instead of raising a `ValueError`. Otherwise, it defaults to `"no_default"`,
            so that the method may raise a `ValueError`.
        print_all_options: whether to print all available options when `opt_str` is not found. Defaults to True

    Examples:

    .. code-block:: python

        from enum import Enum
        from sparkwheel.utils import look_up_option
        class Color(Enum):
            RED = "red"
            BLUE = "blue"
        look_up_option("red", Color)  # <Color.RED: 'red'>
        look_up_option(Color.RED, Color)  # <Color.RED: 'red'>
        look_up_option("read", Color)
        # ValueError: By 'read', did you mean 'red'?
        # 'read' is not a valid option.
        # Available options are {'blue', 'red'}.
        look_up_option("red", {"red", "blue"})  # "red"
    """
    if not isinstance(opt_str, Hashable):
        raise ValueError(f"Unrecognized option type: {type(opt_str)}:{opt_str}.")
    if isinstance(opt_str, str):
        opt_str = opt_str.strip()
    if isinstance(supported, enum.EnumMeta):
        if isinstance(opt_str, str) and opt_str in {item.value for item in supported}:  # type: ignore
            # such as: "example" in MyEnum
            return supported(opt_str)
        if isinstance(opt_str, enum.Enum) and opt_str in supported:
            # such as: MyEnum.EXAMPLE in MyEnum
            return opt_str
    elif isinstance(supported, dict) and opt_str in supported:
        # such as: MyDict[key]
        return supported[opt_str]
    elif isinstance(supported, Collection) and opt_str in supported:
        return opt_str

    if default != "no_default":
        return default

    # find a close match
    set_to_check: set
    if isinstance(supported, enum.EnumMeta):
        set_to_check = {item.value for item in supported}  # type: ignore
    else:
        set_to_check = set(supported) if supported is not None else set()
    if not set_to_check:
        raise ValueError(f"No options available: {supported}.")
    edit_dists = {}
    opt_str = f"{opt_str}"
    for key in set_to_check:
        edit_dist = damerau_levenshtein_distance(f"{key}", opt_str)
        if edit_dist <= 3:
            edit_dists[key] = edit_dist

    supported_msg = f"Available options are {set_to_check}.\n" if print_all_options else ""
    if edit_dists:
        guess_at_spelling = min(edit_dists, key=edit_dists.get)  # type: ignore
        raise ValueError(
            f"By '{opt_str}', did you mean '{guess_at_spelling}'?\n" + f"'{opt_str}' is not a valid value.\n" + supported_msg
        )
    raise ValueError(f"Unsupported option '{opt_str}', " + supported_msg)


class OptionalImportError(ImportError):
    """
    Could not import APIs from an optional dependency.
    """


def optional_import(
    module: str,
    version: str = "",
    name: str = "",
) -> tuple[Any, bool]:
    """
    Imports an optional module specified by `module` string.
    Any importing related exceptions will be stored, and exceptions raise lazily
    when attempting to use the failed-to-import module.

    Args:
        module: name of the module to be imported.
        version: version string (currently not checked, for future use).
        name: a non-module attribute (such as method/class) to import from the imported module.

    Returns:
        The imported module and a boolean flag indicating whether the import is successful.

    Examples::

        >>> yaml, flag = optional_import('yaml')
        >>> print(flag)
        True

        >>> the_module, flag = optional_import('unknown_module')
        >>> print(flag)
        False
        >>> the_module.method  # trying to access a module which is not imported
        OptionalImportError: import unknown_module (No module named 'unknown_module').
    """
    exception_str = ""
    if name:
        actual_cmd = f"from {module} import {name}"
    else:
        actual_cmd = f"import {module}"
    try:
        the_module = import_module(module)
        if name:  # user specified to load class/function/... from the module
            the_module = getattr(the_module, name)
        return the_module, True
    except Exception as import_exception:
        exception_str = f"{import_exception}"

    # Return a placeholder that raises on access
    class _LazyRaise:
        def __getattr__(self, name):
            msg = f"{actual_cmd}"
            if exception_str:
                msg += f" ({exception_str})"
            raise OptionalImportError(msg)

    return _LazyRaise(), False


def instantiate(__path: str, __mode: str, **kwargs: Any) -> Any:
    """
    Create an object instance or call a callable object from a class or function represented by ``__path``.
    `kwargs` will be part of the input arguments to the class constructor or function.
    The target component must be a class or a function, if not, return the component directly.

    Args:
        __path: if a string is provided, it's interpreted as the full path of the target class or function component.
            If a callable is provided, ``__path(**kwargs)`` will be invoked and returned for ``__mode="default"``.
            For ``__mode="callable"``, the callable will be returned as ``__path`` or, if ``kwargs`` are provided,
            as ``functools.partial(__path, **kwargs)`` for future invoking.

        __mode: the operating mode for invoking the (callable) ``component`` represented by ``__path``:

            - ``"default"``: returns ``component(**kwargs)``
            - ``"callable"``: returns ``component`` or, if ``kwargs`` are provided, ``functools.partial(component, **kwargs)``
            - ``"debug"``: returns ``pdb.runcall(component, **kwargs)``

        kwargs: keyword arguments to the callable represented by ``__path``.
    """
    component = locate(__path) if isinstance(__path, str) else __path
    if component is None:
        raise ModuleNotFoundError(f"Cannot locate class or function path: '{__path}'.")
    m = look_up_option(__mode, CompInitMode)
    try:
        if kwargs.pop("_debug_", False) or run_debug:
            warnings.warn(
                f"\n\npdb: instantiating component={component}, mode={m}\n"
                f"See also Debugger commands documentation: https://docs.python.org/3/library/pdb.html\n",
                stacklevel=2,
            )
            breakpoint()
        if not callable(component):
            warnings.warn(f"Component {component} is not callable when mode={m}.", stacklevel=2)
            return component
        if m == CompInitMode.DEFAULT:
            return component(**kwargs)
        if m == CompInitMode.CALLABLE:
            return partial(component, **kwargs) if kwargs else component
        if m == CompInitMode.DEBUG:
            warnings.warn(
                f"\n\npdb: instantiating component={component}, mode={m}\n"
                f"See also Debugger commands documentation: https://docs.python.org/3/library/pdb.html\n",
                stacklevel=2,
            )
            return pdb.runcall(component, **kwargs)
    except Exception as e:
        # Preserve the original exception type and message for better debugging
        error_msg = (
            f"Failed to instantiate component '{__path}' with keywords: {','.join(kwargs.keys())}\n"
            f"  Original error ({type(e).__name__}): {str(e)}\n"
            f"  Set '_mode_={CompInitMode.DEBUG}' to enter debugging mode."
        )
        raise InstantiationError(error_msg) from e

    warnings.warn(f"Component to instantiate must represent a valid class or function, but got {__path}.", stacklevel=2)
    return component
