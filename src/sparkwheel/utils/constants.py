__all__ = [
    "RESOLVED_REF_KEY",
    "RAW_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "REMOVE_KEY",
    "COMBINE_KEY",
    "SIMILARITY_THRESHOLD",
]

RESOLVED_REF_KEY = "@"  # start of a resolved reference (to instantiated/evaluated value)
RAW_REF_KEY = "%"  # start of a raw reference (to unprocessed YAML content)
ID_SEP_KEY = "::"  # separator for the ID of an Item
EXPR_KEY = "$"  # start of an Expression
REMOVE_KEY = "~"  # remove operator for config modifications (delete keys/items)
COMBINE_KEY = "+"  # combine operator: merge a dict into a dict, append a list to a list
SIMILARITY_THRESHOLD = 0.6  # minimum similarity score for key name suggestions (0-1)
