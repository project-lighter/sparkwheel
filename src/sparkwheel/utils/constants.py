__all__ = [
    "RESOLVED_REF_KEY",
    "RAW_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "REMOVE_KEY",
    "REPLACE_KEY",
]

RESOLVED_REF_KEY = "@"  # start of a resolved reference (to instantiated/evaluated value)
RAW_REF_KEY = "%"  # start of a raw reference (to unprocessed YAML content)
ID_SEP_KEY = "::"  # separator for the ID of an Item
EXPR_KEY = "$"  # start of an Expression
REMOVE_KEY = "~"  # remove operator for config modifications (delete keys/items)
REPLACE_KEY = "="  # replace operator for config modifications (explicit override)
