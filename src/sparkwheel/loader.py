"""YAML configuration loading with source location tracking."""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from .metadata import MetadataRegistry
from .utils import CheckKeyDuplicatesYamlLoader, PathLike
from .utils.constants import ID_SEP_KEY
from .utils.exceptions import SourceLocation

__all__ = ["Loader"]


class MetadataTrackingYamlLoader(CheckKeyDuplicatesYamlLoader):
    """YAML loader that tracks source locations into MetadataRegistry.

    Unlike the old approach that added __sparkwheel_metadata__ keys to dicts,
    this loader populates a separate MetadataRegistry during loading.
    """

    def __init__(self, stream, filepath: str, registry: MetadataRegistry):
        super().__init__(stream)
        self.filepath = filepath
        self.registry = registry
        self.id_path_stack: list[str] = []  # Track current path during construction

    def construct_mapping(self, node, deep=False):
        """Override to track source locations for dict nodes."""
        mapping = super().construct_mapping(node, deep=deep)

        # Register source location for this dict node
        if self.id_path_stack:
            id_path = ID_SEP_KEY.join(self.id_path_stack)
        else:
            id_path = ""

        if node.start_mark:
            location = SourceLocation(
                filepath=self.filepath,
                line=node.start_mark.line + 1,
                column=node.start_mark.column + 1,
                id=id_path,
            )
            self.registry.register(id_path, location)

        return mapping


class Loader:
    """Load YAML configuration files with source location tracking.

    Handles loading YAML files and tracking where each config item came from,
    without polluting the config dictionaries with metadata keys.

    Example:
        ```python
        loader = Loader()
        config, metadata = loader.load_file("config.yaml")

        # config is clean dict with no metadata pollution
        print(config["model"]["lr"])  # 0.001

        # metadata tracked separately
        location = metadata.get("model::lr")
        print(f"Defined at {location.filepath}:{location.line}")
        ```
    """

    suffixes = ("yaml", "yml")
    path_pattern = re.compile(r".*\.(yaml|yml)$", re.IGNORECASE)

    def load_file(self, filepath: PathLike) -> tuple[dict, MetadataRegistry]:
        """Load a single YAML file with metadata tracking.

        Args:
            filepath: Path to YAML file

        Returns:
            Tuple of (config_dict, metadata_registry)

        Raises:
            ValueError: If file is not a YAML file
        """
        if not filepath:
            return {}, MetadataRegistry()

        filepath_str = str(Path(filepath))

        # Validate YAML extension
        if not self.path_pattern.match(filepath_str):
            raise ValueError(f'Unknown file input: "{filepath}", must be a YAML file (.yaml or .yml)')

        # Resolve path (detect potential path traversal)
        resolved_path = Path(filepath_str).resolve()
        if ".." in str(filepath):
            warnings.warn(
                f"Config file path contains '..' (parent directory reference): {filepath}\n"
                f"Resolved to: {resolved_path}\n"
                f"This is allowed but ensure the path is from a trusted source to prevent path traversal attacks.",
                UserWarning,
                stacklevel=2,
            )

        # Load YAML with metadata tracking
        registry = MetadataRegistry()
        with open(resolved_path) as f:
            config = self._load_yaml_with_metadata(f, str(resolved_path), registry)

        # Strip metadata keys from config (they're now in registry)
        config = self._strip_metadata(config)

        return config, registry

    def _load_yaml_with_metadata(self, stream, filepath: str, registry: MetadataRegistry) -> dict:
        """Load YAML and populate metadata registry during construction.

        Args:
            stream: File stream to load from
            filepath: Path string for error messages
            registry: MetadataRegistry to populate

        Returns:
            Config dictionary (clean, no metadata keys)
        """

        # Create custom loader class with metadata tracking
        class TrackerLoader(MetadataTrackingYamlLoader):
            pass

        # Bind the filepath and registry to this specific loader instance
        def loader_init(self, stream_arg):
            MetadataTrackingYamlLoader.__init__(self, stream_arg, filepath, registry)

        TrackerLoader.__init__ = loader_init

        # Load and return clean config
        config = yaml.load(stream, TrackerLoader)
        return config if config is not None else {}

    @staticmethod
    def _strip_metadata(config: Any) -> Any:
        """Remove __sparkwheel_metadata__ keys from config.

        Args:
            config: Config structure potentially containing metadata keys

        Returns:
            Config with metadata keys removed
        """
        if isinstance(config, dict):
            return {k: Loader._strip_metadata(v) for k, v in config.items() if k != "__sparkwheel_metadata__"}
        elif isinstance(config, list):
            return [Loader._strip_metadata(item) for item in config]
        else:
            return config

    def load_files(self, filepaths: Sequence[PathLike]) -> tuple[dict, MetadataRegistry]:
        """Load multiple YAML files sequentially.

        Files are loaded in order and merged using simple dict update
        (not the merge_configs logic - that happens at a higher level).

        Args:
            filepaths: Sequence of file paths to load

        Returns:
            Tuple of (merged_config_dict, merged_metadata_registry)
        """
        combined_config = {}
        combined_registry = MetadataRegistry()

        for filepath in filepaths:
            config, registry = self.load_file(filepath)
            combined_config.update(config)
            combined_registry.merge(registry)

        return combined_config, combined_registry
