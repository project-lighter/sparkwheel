__all__ = [
    "ID_REF_KEY",
    "ID_SEP_KEY",
    "EXPR_KEY",
    "MACRO_KEY",
    "DELETE_KEY",
    "MERGE_KEY",
]

ID_REF_KEY = "@"  # start of a reference to a ConfigItem
ID_SEP_KEY = "::"  # separator for the ID of a ConfigItem
EXPR_KEY = "$"  # start of a ConfigExpression
MACRO_KEY = "%"  # start of a macro of a config
DELETE_KEY = "~"  # delete directive for CLI overrides
MERGE_KEY = "+"  # merge directive for CLI overrides
