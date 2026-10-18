"""YAML configuration loading with source location tracking."""

import os
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from yaml.constructor import ConstructorError  # type: ignore[import-untyped]

from .locations import LocationRegistry
from .path_utils import is_yaml_file
from .utils import PathLike
from .utils.constants import ID_SEP_KEY
from .utils.exceptions import Location

__all__ = ["Loader", "YamlLoader"]


class YamlLoader(yaml.SafeLoader):
    """SafeLoader that also reads YAML 1.2 floats such as ``1e-3`` (YAML 1.1 reads them as strings).

    Used for config files and for values in CLI overrides, so both are typed the same way.
    """


YamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^[-+]?(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9][0-9_]*)[eE][-+]?[0-9]+$"),
    list("-+0123456789."),
)


class MetadataTrackingYamlLoader(YamlLoader):
    """YAML loader that tracks source locations into a LocationRegistry and rejects duplicate keys."""

    def __init__(self, stream, filepath: str, registry: LocationRegistry):  # type: ignore[no-untyped-def]
        super().__init__(stream)
        self.filepath = filepath
        self.registry = registry
        self.id_path_stack: list[str] = []  # Track current path during construction

    def construct_mapping(self, node, deep=False):
        """Construct a dict, tracking source locations, expanding `<<:` merge keys and rejecting duplicate keys."""
        # Register source location for this dict node
        current_id = ID_SEP_KEY.join(self.id_path_stack) if self.id_path_stack else ""

        if node.start_mark and current_id not in self.registry:  # a nested node keeps its key's line
            location = Location(
                filepath=self.filepath,
                line=node.start_mark.line + 1,
                column=node.start_mark.column + 1,
                id=current_id,
            )
            self.registry.register(current_id, location)

        # Keys written in this mapping (merged-in keys may legitimately be overridden by them)
        authored = {id(key_node) for key_node, _ in node.value}
        self.flatten_mapping(node)

        mapping = {}
        first_marks: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            if id(key_node) in authored:
                if key in first_marks:
                    first_line = first_marks[key].line + 1
                    problem = f"found duplicate key '{key}' (first defined on line {first_line})"
                    raise ConstructorError(None, None, problem, key_node.start_mark)
                first_marks[key] = key_node.start_mark

            # Push key onto path stack before constructing value
            self.id_path_stack.append(str(key))

            # Register source location for this specific key
            # This allows us to track where each key was defined
            key_id = ID_SEP_KEY.join(self.id_path_stack)
            if key_node.start_mark:
                key_location = Location(
                    filepath=self.filepath,
                    line=key_node.start_mark.line + 1,
                    column=key_node.start_mark.column + 1,
                    id=key_id,
                )
                self.registry.register(key_id, key_location)

            # Construct value with updated path
            mapping[key] = self.construct_object(value_node, deep=True)
            self.id_path_stack.pop()

        return mapping

    def construct_sequence(self, node, deep=False):
        """Construct a list, tracking source locations of its items."""
        # Register source location for this list node
        current_id = ID_SEP_KEY.join(self.id_path_stack) if self.id_path_stack else ""

        if node.start_mark and current_id not in self.registry:  # a nested node keeps its key's line
            location = Location(
                filepath=self.filepath,
                line=node.start_mark.line + 1,
                column=node.start_mark.column + 1,
                id=current_id,
            )
            self.registry.register(current_id, location)

        sequence = []
        for idx, child_node in enumerate(node.value):
            self.id_path_stack.append(str(idx))
            sequence.append(self.construct_object(child_node, deep=True))
            self.id_path_stack.pop()

        return sequence


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

    def load_file(self, filepath: PathLike) -> tuple[dict[str, Any], LocationRegistry]:
        """Load a single YAML file with metadata tracking.

        Args:
            filepath: Path to YAML file

        Returns:
            Tuple of (config_dict, metadata_registry)

        Raises:
            ValueError: If file is not a YAML file
            yaml.YAMLError: If the file is not valid YAML or repeats a key
        """
        if not filepath:
            return {}, LocationRegistry()

        filepath_str = os.path.expanduser(str(Path(filepath)))

        # Validate YAML extension
        if not is_yaml_file(filepath_str):
            raise ValueError(f'Unknown file input: "{filepath}", must be a YAML file (.yaml or .yml)')

        # Load YAML with metadata tracking
        resolved_path = Path(filepath_str).resolve()
        registry = LocationRegistry()
        with open(resolved_path) as f:
            try:
                config = self._load_yaml_with_metadata(f, str(resolved_path), registry)
            except yaml.scanner.ScannerError as e:  # `lr: @base`: YAML cannot start a plain value with @ or %
                char = next((c for c in "@%" if e.problem == f"found character '{c}' that cannot start any token"), None)
                if char:
                    e.problem += f'. Quote a value that starts with {char}: "{char}key"'
                raise

        return config, registry

    def _load_yaml_with_metadata(self, stream, filepath: str, registry: LocationRegistry) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        """Load YAML and populate metadata registry during construction.

        Args:
            stream: File stream to load from
            filepath: Path string for error messages
            registry: LocationRegistry to populate

        Returns:
            Config dictionary (clean, no metadata keys)
        """

        # Create custom loader class with metadata tracking
        class TrackerLoader(MetadataTrackingYamlLoader):
            pass

        # Bind the filepath and registry to this specific loader instance
        def loader_init(self, stream_arg):
            MetadataTrackingYamlLoader.__init__(self, stream_arg, filepath, registry)

        TrackerLoader.__init__ = loader_init  # type: ignore[method-assign,assignment]

        # Load and return clean config
        config = yaml.load(stream, TrackerLoader)
        return config if config is not None else {}
