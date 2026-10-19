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

    def pop(self, id_path: str) -> Location | None:
        """Remove and return the location of ``id_path`` alone (not of the keys under it)."""
        return self._locations.pop(id_path, None)

    def remove_tree(self, id_path: str) -> None:
        """Remove the locations of ``id_path`` and every key under it."""
        prefix = f"{id_path}::"
        for key in [k for k in self._locations if k == id_path or k.startswith(prefix)]:
            del self._locations[key]

    def shift(self, id_path: str, offset: int) -> None:
        """Move the locations of the items of the list ``id_path`` by ``offset`` (for items appended to it)."""
        prefix = f"{id_path}::"
        moved = {}
        for key in [k for k in self._locations if k.startswith(prefix)]:
            index, _, rest = key[len(prefix) :].partition("::")
            if index.isdigit():
                new_key = f"{prefix}{int(index) + offset}" + (f"::{rest}" if rest else "")
                moved[new_key] = self._locations.pop(key)
        self._locations.update(moved)

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
