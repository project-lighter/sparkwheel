"""Configuration preprocessing before parsing.

Handles transformations on raw config dicts before Items are created:
- Raw reference expansion (% references to external files or local YAML)
- Relative ID resolution (@::, @:::: → absolute paths)
"""

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional

from .path_utils import get_by_id, resolve_relative_ids, split_file_and_id
from .utils.constants import ID_SEP_KEY, RAW_REF_KEY
from .utils.exceptions import CircularReferenceError, ConfigKeyError

if TYPE_CHECKING:
    from .locations import LocationRegistry

__all__ = ["Preprocessor"]


class Preprocessor:
    """Preprocess raw config before parsing into Items.

    Pipeline: Raw YAML dict → Preprocessor → Parser → Resolver → Final values

    This is the first processing stage after loading YAML:
    - Expands % raw references (loads external files or local YAML and copies values)
    - Converts relative IDs (@::, @::::) to absolute paths (@)

    Operates on raw Python dicts/lists, not on Item objects.

    ## Two-Phase Raw Reference Expansion

    Raw references are expanded in two phases to support CLI overrides:

    **Phase 1 (Eager, during update()):**
    - External file refs (`%file.yaml::key`) are expanded immediately
    - The external file is frozen - its contents won't change

    **Phase 2 (Lazy, during resolve()):**
    - Local refs (`%key`) are expanded after all composition
    - This allows CLI overrides to affect values referenced by local `%` refs

    Example:
        >>> loader = Loader()
        >>> preprocessor = Preprocessor(loader)
        >>>
        >>> raw_config = {
        ...     "lr": 0.001,
        ...     "base": "%defaults.yaml::learning_rate",  # External - expanded eagerly
        ...     "ref": "%lr",  # Local - expanded lazily
        ...     "model": {
        ...         "lr": "@::lr"  # Relative resolved reference
        ...     }
        ... }
        >>>
        >>> # Phase 1: Expand only external refs
        >>> preprocessed = preprocessor.process_raw_refs(raw_config, raw_config, external_only=True)
        >>> # Result: base=0.0005, ref="%lr" (still string)
        >>>
        >>> # Phase 2: Expand local refs (after CLI overrides applied)
        >>> preprocessed = preprocessor.process_raw_refs(preprocessed, preprocessed, external_only=False)
        >>> # Result: ref=0.001 (now expanded)
    """

    def __init__(self, loader, globals: dict[str, Any] | None = None):  # type: ignore[no-untyped-def]
        """Initialize preprocessor.

        Args:
            loader: Loader instance for loading external raw reference files
            globals: Global context (unused here, kept for API consistency)
        """
        self.loader = loader
        self.globals = globals or {}

    def process_raw_refs(
        self,
        config: Any,
        base_data: dict[str, Any],
        id: str = "",
        locations: Optional["LocationRegistry"] = None,
        *,
        external_only: bool = False,
    ) -> Any:
        """Preprocess config tree - expand % raw references.

        Supports two-phase expansion for CLI override compatibility:

        **Phase 1 (external_only=True, during update()):**
        - Only expands external file refs (`%file.yaml::key`)
        - Local refs (`%key`) are kept as strings for later expansion
        - This allows CLI overrides to affect values used by local refs

        **Phase 2 (external_only=False, during resolve()):**
        - Expands all remaining local refs (`%key`)
        - At this point, all CLI overrides have been applied

        Also handles relative syntax: %::key, %::::key (converted to absolute before expansion)

        Leaves @ resolved references untouched (they're processed lazily during resolve()).

        Args:
            config: Raw config structure to process
            base_data: Root config dict (for resolving local raw references)
            id: Current ID path in tree
            locations: LocationRegistry for error reporting (optional)
            external_only: If True, only expand external file refs (Phase 1).
                          If False, expand all refs including local (Phase 2).

        Returns:
            Config with raw references expanded (or partially expanded if external_only=True)

        Raises:
            CircularReferenceError: If circular raw reference detected
            ConfigKeyError: If referenced key not found
        """
        return self._process_raw_refs_recursive(config, base_data, id, set(), locations, external_only)

    def process(self, config: Any, base_data: dict[str, Any], id: str = "") -> Any:
        """Preprocess entire config tree.

        Main entry point - walks config tree recursively and applies
        all preprocessing transformations. This is the second preprocessing stage
        that runs lazily during resolve(), handling relative IDs and @ references.

        Args:
            config: Raw config structure to process
            base_data: Root config dict (for resolving local macros)
            id: Current ID path in tree (for relative ID resolution)

        Returns:
            Preprocessed config ready for parsing

        Raises:
            CircularReferenceError: If circular raw reference detected
        """
        return self._process_recursive(config, base_data, id, set())

    def _process_raw_refs_recursive(
        self,
        config: Any,
        base_data: dict[str, Any],
        id: str,
        raw_ref_stack: set[str],
        locations: Optional["LocationRegistry"] = None,
        external_only: bool = False,
    ) -> Any:
        """Internal recursive implementation for expanding raw references.

        This method expands % raw references and leaves @ references untouched.
        When external_only=True, only external file refs are expanded.

        Performance optimization: Skips recursion for nodes that don't contain any
        raw reference strings, avoiding unnecessary tree traversal.

        Args:
            config: Current config node
            base_data: Root config dict
            id: Current ID path
            raw_ref_stack: Circular reference detection
            locations: LocationRegistry for error reporting (optional)
            external_only: If True, skip local refs (expand only external file refs)

        Returns:
            Config with raw references expanded (or partially if external_only=True)
        """
        # Early exit optimization: Skip processing if this subtree has no raw references
        # This avoids unnecessary recursion for large config sections without % refs
        if not self._contains_raw_refs(config):
            return config

        # Recursively process nested structures
        if isinstance(config, dict):
            for key in list(config.keys()):
                sub_id = f"{id}{ID_SEP_KEY}{key}" if id else str(key)
                config[key] = self._process_raw_refs_recursive(
                    config[key], base_data, sub_id, raw_ref_stack, locations, external_only
                )

        elif isinstance(config, list):
            for idx in range(len(config)):
                sub_id = f"{id}{ID_SEP_KEY}{idx}" if id else str(idx)
                config[idx] = self._process_raw_refs_recursive(
                    config[idx], base_data, sub_id, raw_ref_stack, locations, external_only
                )

        # Process string values - only expand raw references (%)
        if isinstance(config, str):
            # First resolve relative IDs in raw references (e.g., %::key -> %parent::key)
            # This is necessary because raw references can use relative syntax
            config = resolve_relative_ids(id, config)

            # Then expand raw references
            if config.startswith(RAW_REF_KEY):
                config = self._expand_raw_ref(config, base_data, raw_ref_stack, id, locations, external_only)

        return config

    def _process_recursive(
        self,
        config: Any,
        base_data: dict[str, Any],
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

            # Step 2: Expand raw references (%) - should already be expanded, but keep for safety
            if config.startswith(RAW_REF_KEY):
                config = self._expand_raw_ref(config, base_data, raw_ref_stack)

        return config

    def _expand_raw_ref(
        self,
        raw_ref: str,
        base_data: dict[str, Any],
        raw_ref_stack: set[str],
        current_id: str = "",
        locations: Optional["LocationRegistry"] = None,
        external_only: bool = False,
    ) -> Any:
        """Expand a single raw reference by loading external file or local YAML.

        Args:
            raw_ref: Raw reference string (e.g., "%file.yaml::key" or "%key")
            base_data: Root config for local raw references
            raw_ref_stack: Circular reference detection
            current_id: Current ID path (where this raw reference was found)
            locations: LocationRegistry for error reporting (optional)
            external_only: If True, skip local refs and return raw_ref unchanged

        Returns:
            Value from raw reference (deep copied), or raw_ref unchanged if
            external_only=True and this is a local reference

        Raises:
            CircularReferenceError: If circular reference detected
            ConfigKeyError: If referenced key not found
        """
        # Parse: "%file.yaml::key" → ("file.yaml", "key")
        path, ids = split_file_and_id(raw_ref[len(RAW_REF_KEY) :])

        # Phase 1 (external_only=True): Skip local refs, they'll be expanded later
        # This allows CLI overrides to affect values used by local % refs
        is_local_ref = not path
        if external_only and is_local_ref:
            return raw_ref  # Keep as string, expand in Phase 2

        # Circular reference check
        if raw_ref in raw_ref_stack:
            chain = " -> ".join(sorted(raw_ref_stack))

            # Get location information if available
            location = None
            if locations and current_id:
                location = locations.get(current_id)

            raise CircularReferenceError(
                message=f"Circular raw reference detected: '{raw_ref}'\nReference chain: {chain} -> {raw_ref}",
                source_location=location,
            )

        raw_ref_stack.add(raw_ref)

        try:
            # Load config (external file or local)
            if is_local_ref:
                loaded_config = base_data  # Local raw reference: %key
                loaded_locations = locations  # Use same location registry
                source_description = "local config"
            else:
                loaded_config, loaded_locations = self.loader.load_file(path)  # External: %file.yaml::key
                source_description = f"'{path}'"

            # Navigate to referenced value
            try:
                result = get_by_id(loaded_config, ids)
            except (KeyError, TypeError, IndexError) as e:
                # Get location information if available
                location = None
                if locations and current_id:
                    location = locations.get(current_id)

                # Build error message
                if is_local_ref:
                    error_msg = f"Error resolving raw reference '{raw_ref}' from local config:\n{e}"
                else:
                    error_msg = f"Error resolving raw reference '{raw_ref}' from {source_description}:\n{e}"

                # Raise custom error with proper formatting
                raise ConfigKeyError(
                    message=error_msg,
                    source_location=location,
                ) from e

            # Recursively preprocess the loaded value (expand nested raw references)
            # For external files, always expand all refs within that file
            # For local refs (Phase 2), expand all nested refs too
            result = self._process_raw_refs_recursive(
                result, loaded_config, ids, raw_ref_stack, loaded_locations, external_only=False
            )

            # Deep copy for independence
            return deepcopy(result)

        finally:
            raw_ref_stack.discard(raw_ref)

    @staticmethod
    def _contains_raw_refs(config: Any) -> bool:
        """Check if a config node or its descendants contain any raw references.

        Performance optimization to skip processing subtrees without % references.

        Args:
            config: Config node to check

        Returns:
            True if any raw references found, False otherwise
        """
        if isinstance(config, str):
            return config.startswith(RAW_REF_KEY)
        elif isinstance(config, dict):
            return any(Preprocessor._contains_raw_refs(v) for v in config.values())
        elif isinstance(config, list):
            return any(Preprocessor._contains_raw_refs(item) for item in config)
        return False
