"""Configuration preprocessing before parsing.

Handles transformations on raw config dicts before Items are created:
- Raw reference expansion (% references to external files or local YAML)
- Relative ID resolution (@::, @:::: → absolute paths)
"""

from copy import deepcopy
from typing import Any

from .path_patterns import split_file_and_id
from .path_utils import resolve_relative_ids, split_id
from .utils.constants import ID_SEP_KEY, RAW_REF_KEY

__all__ = ["Preprocessor"]


class Preprocessor:
    """Preprocess raw config before parsing into Items.

    Pipeline: Raw YAML dict → Preprocessor → Parser → Resolver → Final values

    This is the first processing stage after loading YAML:
    - Expands % raw references (loads external files or local YAML and copies values)
    - Converts relative IDs (@::, @::::) to absolute paths (@)

    Operates on raw Python dicts/lists, not on Item objects.

    Example:
        >>> loader = Loader()
        >>> preprocessor = Preprocessor(loader)
        >>>
        >>> raw_config = {
        ...     "lr": 0.001,
        ...     "base": "%defaults.yaml::learning_rate",  # Raw reference (external)
        ...     "model": {
        ...         "lr": "@::lr"  # Relative resolved reference
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
            loader: Loader instance for loading external raw reference files
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
            ValueError: If circular raw reference detected
        """
        return self._process_recursive(config, base_data, id, set())

    def _process_recursive(
        self,
        config: Any,
        base_data: dict,
        id: str,
        raw_ref_stack: set[str],
    ) -> Any:
        """Internal recursive preprocessing implementation.

        Args:
            config: Current config node
            base_data: Root config dict
            id: Current ID path
            raw_ref_stack: Circular reference detection

        Returns:
            Preprocessed config
        """
        # Recursively process nested structures
        if isinstance(config, dict):
            for key in list(config.keys()):
                sub_id = f"{id}{ID_SEP_KEY}{key}" if id else str(key)
                config[key] = self._process_recursive(config[key], base_data, sub_id, raw_ref_stack)

        elif isinstance(config, list):
            for idx in range(len(config)):
                sub_id = f"{id}{ID_SEP_KEY}{idx}" if id else str(idx)
                config[idx] = self._process_recursive(config[idx], base_data, sub_id, raw_ref_stack)

        # Process string values
        if isinstance(config, str):
            # Step 1: Resolve relative IDs (@::, @::::) to absolute (@)
            config = resolve_relative_ids(id, config)

            # Step 2: Expand raw references (%)
            if config.startswith(RAW_REF_KEY):
                config = self._expand_raw_ref(config, base_data, raw_ref_stack)

        return config

    def _expand_raw_ref(self, raw_ref: str, base_data: dict, raw_ref_stack: set[str]) -> Any:
        """Expand a single raw reference by loading external file or local YAML.

        Args:
            raw_ref: Raw reference string (e.g., "%file.yaml::key" or "%key")
            base_data: Root config for local raw references
            raw_ref_stack: Circular reference detection

        Returns:
            Value from raw reference (deep copied)

        Raises:
            ValueError: If circular reference detected
        """
        # Circular reference check
        if raw_ref in raw_ref_stack:
            chain = " -> ".join(sorted(raw_ref_stack))
            raise ValueError(f"Circular raw reference detected: '{raw_ref}'\nRaw reference chain: {chain} -> {raw_ref}")

        # Parse: "%file.yaml::key" → ("file.yaml", "key")
        path, ids = split_file_and_id(raw_ref[len(RAW_REF_KEY) :])

        raw_ref_stack.add(raw_ref)

        try:
            # Load config (external file or local)
            if not path:
                loaded_config = base_data  # Local raw reference: %key
            else:
                loaded_config, _ = self.loader.load_file(path)  # External: %file.yaml::key

            # Navigate to referenced value
            result = self._get_by_id(loaded_config, ids)

            # Recursively preprocess the loaded value
            result = self._process_recursive(result, loaded_config, ids, raw_ref_stack)

            # Deep copy for independence
            return deepcopy(result)

        finally:
            raw_ref_stack.discard(raw_ref)

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
