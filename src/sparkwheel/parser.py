"""Parse configuration tree and create Items."""

from __future__ import annotations

from typing import Any

from .items import Component, Expression, Item
from .metadata import MetadataRegistry
from .utils.constants import ID_SEP_KEY

__all__ = ["Parser"]


class Parser:
    """Parse config tree and create Items with source locations.

    Recursively traverses configuration dictionaries and lists, creating
    appropriate Item subclasses (Component, Expression, or
    plain Item) for each node.

    Example:
        ```python
        config = {
            "lr": 0.001,
            "doubled": "$@lr * 2",
            "optimizer": {
                "_target_": "torch.optim.Adam",
                "lr": "@lr"
            }
        }

        metadata = MetadataRegistry()
        parser = Parser(globals={}, metadata=metadata)
        items = parser.parse(config)

        # Returns list of Items with proper types
        for item in items:
            print(f"{item.id}: {type(item).__name__}")
        # Output:
        # lr: Item
        # doubled: Expression
        # optimizer: Component
        # optimizer::lr: Item (the reference string)
        ```

    Args:
        globals: Global context for expression evaluation
        metadata: MetadataRegistry for source location lookup
    """

    def __init__(self, globals: dict[str, Any], metadata: MetadataRegistry):
        """Initialize parser with globals and metadata.

        Args:
            globals: Dictionary of global variables for expression evaluation
            metadata: MetadataRegistry for looking up source locations
        """
        self._globals = globals
        self._metadata = metadata

    def parse(self, config: Any, id_prefix: str = "") -> list[Item]:
        """Recursively parse config and create Items.

        Args:
            config: Configuration data to parse (dict, list, or primitive)
            id_prefix: ID path prefix for nested items (e.g., "model::optimizer")

        Returns:
            List of all Items created from the config tree
        """
        items: list[Item] = []
        self._parse_recursive(config, id_prefix, items)
        return items

    def _parse_recursive(self, config: Any, id: str, items: list[Item]) -> None:
        """Internal recursive parsing implementation.

        Args:
            config: Current config node to parse
            id: Current ID path
            items: List to accumulate Items (modified in place)
        """
        # Get source location for this config node
        source_location = self._metadata.get(id) if id else None

        # Recursively parse nested structures
        if isinstance(config, dict):
            for key, value in config.items():
                sub_id = f"{id}{ID_SEP_KEY}{key}" if id else str(key)
                self._parse_recursive(value, sub_id, items)
        elif isinstance(config, list):
            for idx, value in enumerate(config):
                sub_id = f"{id}{ID_SEP_KEY}{idx}" if id else str(idx)
                self._parse_recursive(value, sub_id, items)

        # Create appropriate Item for this node
        if Component.is_instantiable(config):
            items.append(Component(config=config, id=id, source_location=source_location))
        elif Expression.is_expression(config):
            items.append(Expression(config=config, id=id, globals=self._globals, source_location=source_location))
        else:
            items.append(Item(config=config, id=id, source_location=source_location))
