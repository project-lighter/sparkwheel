"""Location tracking for configuration keys."""

from sparkwheel.utils.exceptions import Location

__all__ = ["LocationRegistry"]


class LocationRegistry:
    """Registry that tracks file locations for configuration keys.

    Maintains a clean separation between config data and location information
    about where config items came from. This avoids polluting config dictionaries
    with metadata keys.

    Example:
        ```python
        registry = LocationRegistry()
        registry.register("model::lr", Location("config.yaml", 10, 2, "model::lr"))

        location = registry.get("model::lr")
        print(location.filepath)  # "config.yaml"
        print(location.line)      # 10
        ```
    """

    def __init__(self):
        """Initialize empty location registry."""
        self._locations: dict[str, Location] = {}

    def register(self, id_path: str, location: Location) -> None:
        """Register location for a config path.

        Args:
            id_path: Configuration path (e.g., "model::lr", "optimizer::params::0")
            location: Location information
        """
        self._locations[id_path] = location

    def get(self, id_path: str) -> Location | None:
        """Get location for a config path.

        Args:
            id_path: Configuration path to look up

        Returns:
            Location if registered, None otherwise
        """
        return self._locations.get(id_path)

    def merge(self, other: "LocationRegistry") -> None:
        """Merge another registry into this one.

        Args:
            other: LocationRegistry to merge from
        """
        self._locations.update(other._locations)

    def copy(self) -> "LocationRegistry":
        """Create a copy of this registry.

        Returns:
            New LocationRegistry with same data
        """
        new_registry = LocationRegistry()
        new_registry._locations = self._locations.copy()
        return new_registry

    def __len__(self) -> int:
        """Return number of registered locations."""
        return len(self._locations)

    def __contains__(self, id_path: str) -> bool:
        """Check if id_path has registered location."""
        return id_path in self._locations
