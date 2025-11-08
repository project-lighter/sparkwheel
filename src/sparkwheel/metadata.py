"""Source location metadata tracking."""

from __future__ import annotations

from sparkwheel.utils.exceptions import SourceLocation

__all__ = ["MetadataRegistry"]


class MetadataRegistry:
    """Track source locations for config items.

    Maintains a clean separation between config data and metadata about where
    config items came from. This avoids polluting config dictionaries with
    metadata keys.

    Example:
        ```python
        registry = MetadataRegistry()
        registry.register("model::lr", SourceLocation("config.yaml", 10, 2, "model::lr"))

        location = registry.get("model::lr")
        print(location.filepath)  # "config.yaml"
        print(location.line)      # 10
        ```
    """

    def __init__(self):
        """Initialize empty metadata registry."""
        self._locations: dict[str, SourceLocation] = {}

    def register(self, id_path: str, location: SourceLocation) -> None:
        """Register source location for a config path.

        Args:
            id_path: Configuration path (e.g., "model::lr", "optimizer::params::0")
            location: Source location information
        """
        self._locations[id_path] = location

    def get(self, id_path: str) -> SourceLocation | None:
        """Get source location for a config path.

        Args:
            id_path: Configuration path to look up

        Returns:
            SourceLocation if registered, None otherwise
        """
        return self._locations.get(id_path)

    def merge(self, other: "MetadataRegistry") -> None:
        """Merge another registry into this one.

        Args:
            other: MetadataRegistry to merge from
        """
        self._locations.update(other._locations)

    def copy(self) -> "MetadataRegistry":
        """Create a copy of this registry.

        Returns:
            New MetadataRegistry with same data
        """
        new_registry = MetadataRegistry()
        new_registry._locations = self._locations.copy()
        return new_registry

    def __len__(self) -> int:
        """Return number of registered locations."""
        return len(self._locations)

    def __contains__(self, id_path: str) -> bool:
        """Check if id_path has registered location."""
        return id_path in self._locations
