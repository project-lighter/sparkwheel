"""Configuration preprocessing before parsing.

Handles transformations on raw config dicts before Items are created:
- Macro expansion (% references to external files)
- Relative ID resolution (@::, @:::: → absolute paths)
"""

from copy import deepcopy
from typing import Any

from .path_patterns import split_file_and_id
from .path_utils import resolve_relative_ids, split_id
from .utils.constants import ID_SEP_KEY, MACRO_KEY

__all__ = ["Preprocessor"]


class Preprocessor:
    """Preprocess raw config before parsing into Items.

    Pipeline: Raw YAML dict → Preprocessor → Parser → Resolver → Final values

    This is the first processing stage after loading YAML:
    - Expands % macros (loads external files and copies values)
    - Converts relative IDs (@::, @::::) to absolute paths (@)

    Operates on raw Python dicts/lists, not on Item objects.

    Example:
        >>> loader = Loader()
        >>> preprocessor = Preprocessor(loader)
        >>>
        >>> raw_config = {
        ...     "lr": 0.001,
        ...     "base": "%defaults.yaml::learning_rate",  # Macro
        ...     "model": {
        ...         "lr": "@::lr"  # Relative reference
        ...     }
        ... }
        >>>
        >>> preprocessed = preprocessor.process(raw_config, raw_config)
        >>> # Result:
        >>> # {
        >>> #     "lr": 0.001,
        >>> #     "base": 0.0005,  # Loaded from defaults.yaml
        >>> #     "model": {
        >>> #         "lr": "@model::lr"  # Converted to absolute
        >>> #     }
        >>> # }
    """

    def __init__(self, loader, globals: dict[str, Any] | None = None):
        """Initialize preprocessor.

        Args:
            loader: Loader instance for loading external macro files
            globals: Global context (unused here, kept for API consistency)
        """
        self.loader = loader
        self.globals = globals or {}

    def process(self, config: Any, base_data: dict, id: str = "") -> Any:
        """Preprocess entire config tree.

        Main entry point - walks config tree recursively and applies
        all preprocessing transformations.

        Args:
            config: Raw config structure to process
            base_data: Root config dict (for resolving local macros)
            id: Current ID path in tree (for relative ID resolution)

        Returns:
            Preprocessed config ready for parsing

        Raises:
            ValueError: If circular macro reference detected
        """
        return self._process_recursive(config, base_data, id, set())

    def _process_recursive(
        self,
        config: Any,
        base_data: dict,
        id: str,
        macro_stack: set[str],
    ) -> Any:
        """Internal recursive preprocessing implementation.

        Args:
            config: Current config node
            base_data: Root config dict
            id: Current ID path
            macro_stack: Circular reference detection

        Returns:
            Preprocessed config
        """
        # Recursively process nested structures
        if isinstance(config, dict):
            for key in list(config.keys()):
                sub_id = f"{id}{ID_SEP_KEY}{key}" if id else str(key)
                config[key] = self._process_recursive(config[key], base_data, sub_id, macro_stack)

        elif isinstance(config, list):
            for idx in range(len(config)):
                sub_id = f"{id}{ID_SEP_KEY}{idx}" if id else str(idx)
                config[idx] = self._process_recursive(config[idx], base_data, sub_id, macro_stack)

        # Process string values
        if isinstance(config, str):
            # Step 1: Resolve relative IDs (@::, @::::) to absolute (@)
            config = resolve_relative_ids(id, config)

            # Step 2: Expand macros (%)
            if config.startswith(MACRO_KEY):
                config = self._expand_macro(config, base_data, macro_stack)

        return config

    def _expand_macro(self, macro_ref: str, base_data: dict, macro_stack: set[str]) -> Any:
        """Expand a single macro reference by loading external file.

        Args:
            macro_ref: Macro string (e.g., "%file.yaml::key")
            base_data: Root config for local macros
            macro_stack: Circular reference detection

        Returns:
            Value from macro (deep copied)

        Raises:
            ValueError: If circular reference detected
        """
        # Circular reference check
        if macro_ref in macro_stack:
            chain = " -> ".join(sorted(macro_stack))
            raise ValueError(f"Circular macro reference detected: '{macro_ref}'\nMacro chain: {chain} -> {macro_ref}")

        # Parse: "%file.yaml::key" → ("file.yaml", "key")
        path, ids = split_file_and_id(macro_ref[len(MACRO_KEY) :])

        macro_stack.add(macro_ref)

        try:
            # Load config (external file or local)
            if not path:
                loaded_config = base_data  # Local macro: %key
            else:
                loaded_config, _ = self.loader.load_file(path)  # External: %file.yaml::key

            # Navigate to referenced value
            result = self._get_by_id(loaded_config, ids)

            # Recursively preprocess the loaded value
            result = self._process_recursive(result, loaded_config, ids, macro_stack)

            # Deep copy for independence
            return deepcopy(result)

        finally:
            macro_stack.discard(macro_ref)

    @staticmethod
    def _get_by_id(config: dict, id: str) -> Any:
        """Navigate config dict by ID path.

        Args:
            config: Config dict to navigate
            id: ID path (e.g., "model::optimizer::lr")

        Returns:
            Value at ID path

        Raises:
            KeyError: If path not found
            TypeError: If trying to index non-dict/list
        """
        if not id:
            return config

        current = config
        for key in split_id(id):
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, list):
                current = current[int(key)]
            else:
                raise TypeError(f"Cannot index {type(current).__name__} with key '{key}' at path '{id}'")

        return current
