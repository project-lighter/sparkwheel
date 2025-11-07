import re
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from sparkwheel.config_item import ConfigComponent, ConfigExpression, ConfigItem
from sparkwheel.constants import ID_REF_KEY, ID_SEP_KEY, MACRO_KEY
from sparkwheel.reference_resolver import ReferenceResolver
from sparkwheel.utils import CheckKeyDuplicatesYamlLoader, PathLike, ensure_tuple, look_up_option, optional_import

__all__ = ["ConfigParser"]


class ConfigParser:
    """Primary configuration parser for YAML configs with references and expressions.

    Traverses structured configuration (nested dicts/lists), creates ConfigItems,
    and assigns unique IDs. Supports references (`@`), expressions (`$`), and
    dynamic instantiation (`_target_`).

    Example:
        ```python
        from sparkwheel import ConfigParser

        config = {
            "base_count": 10,
            "doubled": "$@base_count * 2",
            "my_counter": {
                "_target_": "collections.Counter",
                "iterable": "@my_list"
            },
            "my_list": [1, 2, 2, 3, 3, 3]
        }

        parser = ConfigParser(config)

        # Access and modify config before parsing
        print(parser["my_counter"]["iterable"])  # "@my_list"
        parser["my_list"] = [1, 1, 1]

        # Parse and instantiate
        parser.parse()
        counter = parser.get_parsed_content("my_counter", instantiate=True)
        print(counter)  # Counter({1: 3})

        # Get parsed values
        doubled = parser.get_parsed_content("doubled")
        print(doubled)  # 20
        ```

    Args:
        config: Configuration source (dict, list, or YAML file path)
        globals: Pre-imported packages for expressions.
            Pass a dict like `{"pd": "pandas", "Path": "pathlib.Path"}` to make
            these packages available in expressions.
    """

    suffixes = ("yaml", "yml")
    suffix_match = rf".*\.({'|'.join(suffixes)})"
    path_match = rf"({suffix_match}$)"
    # match relative id names, e.g. "@#data", "@##transform#1"
    relative_id_prefix = re.compile(rf"(?:{ID_REF_KEY}|{MACRO_KEY}){ID_SEP_KEY}+")
    meta_key = "_meta_"  # field key to save metadata

    def __init__(
        self,
        config: Any = None,
        globals: dict[str, Any] | None | bool = None,
    ):
        self.config: ConfigItem | None = None
        self.globals: dict[str, Any] = {}
        if isinstance(globals, dict):
            for k, v in globals.items():
                self.globals[k] = optional_import(v)[0] if isinstance(v, str) else v

        self.ref_resolver = ReferenceResolver()
        if config is None:
            config = {self.meta_key: {}}
        self.set(config=self.ref_resolver.normalize_meta_id(config))

    def __repr__(self):
        return f"{self.config}"

    def __getattr__(self, id):
        """
        Get the parsed result of ``ConfigItem`` with the specified ``id``
        with default arguments (e.g. ``lazy=True``, ``instantiate=True`` and ``eval_expr=True``).

        Args:
            id: id of the ``ConfigItem``.

        See also:
             :py:meth:`get_parsed_content`
        """
        return self.get_parsed_content(id)

    def __getitem__(self, id: str | int) -> Any:
        """
        Get the config by id.

        Args:
            id: id of the ``ConfigItem``, ``"::"`` (or ``"#"``) in id are interpreted as special characters to
                go one level further into the nested structures.
                Use digits indexing from "0" for list or other strings for dict.
                For example: ``"xform::5"``, ``"net::channels"``. ``""`` indicates the entire ``self.config``.
        """
        if id == "":
            return self.config
        config = self.config
        for k in ReferenceResolver.split_id(id):
            if not isinstance(config, (dict, list)):
                raise ValueError(f"config must be dict or list for key `{k}`, but got {type(config)}: {config}.")
            try:
                config = look_up_option(k, config, print_all_options=False) if isinstance(config, dict) else config[int(k)]
            except ValueError as e:
                raise KeyError(f"query key: {k}") from e
        return config

    def __setitem__(self, id: str | int, config: Any) -> None:
        """
        Set config by ``id``.  Note that this method should be used before ``parse()`` or ``get_parsed_content()``
        to ensure the updates are included in the parsed content.

        Args:
            id: id of the ``ConfigItem``, ``"::"`` (or ``"#"``) in id are interpreted as special characters to
                go one level further into the nested structures.
                Use digits indexing from "0" for list or other strings for dict.
                For example: ``"xform::5"``, ``"net::channels"``. ``""`` indicates the entire ``self.config``.
            config: config to set at location ``id``.
        """
        if id == "":
            self.config = config
            self.ref_resolver.reset()
            return
        last_id, base_id = ReferenceResolver.split_id(id, last=True)
        # get the last parent level config item and replace it
        conf_ = self[last_id]

        indexing = base_id if isinstance(conf_, dict) else int(base_id)
        conf_[indexing] = config
        self.ref_resolver.reset()
        return

    def get(self, id: str = "", default: Any | None = None) -> Any:
        """
        Get the config by id.

        Args:
            id: id to specify the expected position. See also :py:meth:`__getitem__`.
            default: default value to return if the specified ``id`` is invalid.
        """
        try:
            return self[id]
        except (KeyError, IndexError, ValueError):  # Index error for integer indexing
            return default

    def set(self, config: Any, id: str = "", recursive: bool = True) -> None:
        """
        Set config by ``id``.

        Args:
            config: config to set at location ``id``.
            id: id to specify the expected position. See also :py:meth:`__setitem__`.
            recursive: if the nested id doesn't exist, whether to recursively create the nested items in the config.
                default to `True`. for the nested id, only support `dict` for the missing section.
        """
        keys = ReferenceResolver.split_id(id)
        conf_ = self.get()
        if recursive:
            if conf_ is None:
                self.config = conf_ = {}  # type: ignore
            for k in keys[:-1]:
                if isinstance(conf_, dict) and k not in conf_:
                    conf_[k] = {}
                conf_ = conf_[k if isinstance(conf_, dict) else int(k)]
        self[ReferenceResolver.normalize_id(id)] = self.ref_resolver.normalize_meta_id(config)

    def update(self, pairs: dict[str, Any]) -> None:
        """
        Set the ``id`` and the corresponding config content in pairs, see also :py:meth:`__setitem__`.
        For example, ``parser.update({"train::epoch": 100, "train::lr": 0.02})``

        Args:
            pairs: dictionary of `id` and config pairs.
        """
        for k, v in pairs.items():
            self[k] = v

    def __contains__(self, id: str | int) -> bool:
        """
        Returns True if `id` is stored in this configuration.

        Args:
            id: id to specify the expected position. See also :py:meth:`__getitem__`.
        """
        try:
            _ = self[id]
            return True
        except (KeyError, IndexError, ValueError):  # Index error for integer indexing
            return False

    def parse(self, reset: bool = True) -> None:
        """
        Recursively resolve `self.config` to replace the macro tokens with target content.
        Then recursively parse the config source, add every item as ``ConfigItem`` to the reference resolver.

        Args:
            reset: whether to reset the ``reference_resolver`` before parsing. Defaults to `True`.
        """
        if reset:
            self.ref_resolver.reset()
        self.resolve_macro_and_relative_ids()
        self._do_parse(config=self.get())

    def get_parsed_content(self, id: str = "", **kwargs: Any) -> Any:
        """
        Get the parsed result of ``ConfigItem`` with the specified ``id``.

            - If the item is ``ConfigComponent`` and ``instantiate=True``, the result is the instance.
            - If the item is ``ConfigExpression`` and ``eval_expr=True``, the result is the evaluated output.
            - Else, the result is the configuration content of `ConfigItem`.

        Args:
            id: id of the ``ConfigItem``, ``"::"`` (or ``"#"``) in id are interpreted as special characters to
                go one level further into the nested structures.
                Use digits indexing from "0" for list or other strings for dict.
                For example: ``"xform::5"``, ``"net::channels"``. ``""`` indicates the entire ``self.config``.
            kwargs: additional keyword arguments to be passed to ``_resolve_one_item``.
                Currently support ``lazy`` (whether to retain the current config cache, default to `True`),
                ``instantiate`` (whether to instantiate the `ConfigComponent`, default to `True`) and
                ``eval_expr`` (whether to evaluate the `ConfigExpression`, default to `True`), ``default``
                (the default config item if the `id` is not in the config content).
        """
        if not self.ref_resolver.is_resolved():
            # not parsed the config source yet, parse it
            self.parse(reset=True)
        elif not kwargs.get("lazy", True):
            self.parse(reset=not kwargs.get("lazy", True))
        return self.ref_resolver.get_resolved_content(id=id, **kwargs)

    def read_meta(self, f: PathLike | Sequence[PathLike] | dict, **kwargs: Any) -> None:
        """
        Read the metadata from specified YAML file.
        The metadata as a dictionary will be stored at ``self.config["_meta_"]``.

        Args:
            f: filepath of the metadata file, the content must be a dictionary,
                if providing a list of files, will merge the content of them.
                if providing a dictionary directly, use it as metadata.
            kwargs: other arguments for ``yaml.safe_load``.
        """
        self.set(self.load_config_files(f, **kwargs), self.meta_key)

    def read_config(self, f: PathLike | Sequence[PathLike] | dict, **kwargs: Any) -> None:
        """
        Read the config from specified YAML file or a dictionary and
        override the config content in the `self.config` dictionary.

        Args:
            f: filepath of the config file, the content must be a dictionary,
                if providing a list of files, will merge the content of them.
                if providing a dictionary directly, use it as config.
            kwargs: other arguments for ``yaml.safe_load``.
        """
        content = {self.meta_key: self.get(self.meta_key, {})}
        content.update(self.load_config_files(f, **kwargs))
        self.set(config=content)

    def _do_resolve(self, config: Any, id: str = "") -> Any:
        """
        Recursively resolve `self.config` to replace the relative ids with absolute ids, for example,
        `@##A` means `A` in the upper level. and replace the macro tokens with target content,
        The macro tokens start with "%", can be from another structured file, like:
        ``"%default_net"``, ``"%/data/config.yaml#net"``.
        Note that the macro replacement doesn't support recursive macro tokens.

        Args:
            config: input config file to resolve.
            id: id of the ``ConfigItem``, ``"::"`` (or ``"#"``) in id are interpreted as special characters to
                go one level further into the nested structures.
                Use digits indexing from "0" for list or other strings for dict.
                For example: ``"xform::5"``, ``"net::channels"``. ``""`` indicates the entire ``self.config``.
        """
        if isinstance(config, (dict, list)):
            for k, sub_id, v in self.ref_resolver.iter_subconfigs(id=id, config=config):
                config[k] = self._do_resolve(v, sub_id)  # type: ignore
        if isinstance(config, str):
            config = self.resolve_relative_ids(id, config)
            if config.startswith(MACRO_KEY):
                path, ids = ConfigParser.split_path_id(config[len(MACRO_KEY) :])
                parser = ConfigParser(config=self.get() if not path else ConfigParser.load_config_file(path))
                # deepcopy to ensure the macro replacement is independent config content
                return deepcopy(parser[ids])
        return config

    def resolve_macro_and_relative_ids(self):
        """
        Recursively resolve `self.config` to replace the relative ids with absolute ids, for example,
        `@##A` means `A` in the upper level. and replace the macro tokens with target content,
        The macro tokens are marked as starting with "%", can be from another structured file, like:
        ``"%default_net"``, ``"%/data/config.yaml::net"``.
        """
        self.set(self._do_resolve(config=self.get()))

    def _do_parse(self, config: Any, id: str = "") -> None:
        """
        Recursively parse the nested data in config source, add every item as `ConfigItem` to the resolver.

        Args:
            config: config source to parse.
            id: id of the ``ConfigItem``, ``"::"`` (or ``"#"``) in id are interpreted as special characters to
                go one level further into the nested structures.
                Use digits indexing from "0" for list or other strings for dict.
                For example: ``"xform::5"``, ``"net::channels"``. ``""`` indicates the entire ``self.config``.
        """
        if isinstance(config, (dict, list)):
            for _, sub_id, v in self.ref_resolver.iter_subconfigs(id=id, config=config):
                self._do_parse(config=v, id=sub_id)

        if ConfigComponent.is_instantiable(config):
            self.ref_resolver.add_item(ConfigComponent(config=config, id=id))
        elif ConfigExpression.is_expression(config):
            self.ref_resolver.add_item(ConfigExpression(config=config, id=id, globals=self.globals))
        else:
            self.ref_resolver.add_item(ConfigItem(config=config, id=id))

    @classmethod
    def load_config_file(cls, filepath: PathLike, **kwargs: Any) -> dict:
        """
        Load a single config file with specified file path (currently support YAML files only).

        Args:
            filepath: path of target file to load, supported postfixes: `.yml`, `.yaml`.
            kwargs: other arguments for ``yaml.safe_load``.
        """
        if not filepath:
            return {}
        _filepath: str = str(Path(filepath))
        if not re.compile(cls.path_match, re.IGNORECASE).findall(_filepath):
            raise ValueError(f'unknown file input: "{filepath}", must be a YAML file (.yaml or .yml)')
        with open(_filepath) as f:
            if _filepath.lower().endswith(cls.suffixes):
                return yaml.load(f, CheckKeyDuplicatesYamlLoader, **kwargs)  # type: ignore[no-any-return]
            raise ValueError(f"only support YAML config file, got name {_filepath}.")

    @classmethod
    def load_config_files(cls, files: PathLike | Sequence[PathLike] | dict, **kwargs: Any) -> dict:
        """
        Load multiple config files into a single config dict.
        The latter config file in the list will override or add the former config file.
        ``"::"`` (or ``"#"``) in the config keys are interpreted as special characters to go one level
        further into the nested structures.

        Args:
            files: path of target files to load, supported postfixes: `.yml`, `.yaml`.
                if providing a list of files, will merge the content of them.
                if providing a string with comma separated file paths, will merge the content of them.
                if providing a dictionary, return it directly.
            kwargs: other arguments for ``yaml.safe_load``.
        """
        if isinstance(files, dict):  # already a config dict
            return files
        parser = ConfigParser(config={})
        if isinstance(files, str) and not Path(files).is_file() and "," in files:
            files = files.split(",")
        for i in ensure_tuple(files):
            config_dict = cls.load_config_file(i, **kwargs)
            for k, v in config_dict.items():
                parser.set(v, k)

        return parser.get()  # type: ignore

    @classmethod
    def export_config_file(cls, config: dict, filepath: PathLike, **kwargs: Any) -> None:
        """
        Export the config content to the specified file path (YAML format).

        Args:
            config: source config content to export.
            filepath: target file path to save.
            kwargs: other arguments for ``yaml.safe_dump``.
        """
        _filepath: str = str(Path(filepath))
        with open(_filepath, "w") as f:
            yaml.safe_dump(config, f, **kwargs)

    @classmethod
    def split_path_id(cls, src: str) -> tuple[str, str]:
        """
        Split `src` string into two parts: a config file path and component id.
        The file path should end with `(yaml|yml)`. The component id should be separated by `::` if it exists.
        If no path or no id, return "".

        Args:
            src: source string to split.
        """
        src = ReferenceResolver.normalize_id(src)
        result = re.compile(rf"({cls.suffix_match}(?=(?:{ID_SEP_KEY}.*)|$))", re.IGNORECASE).findall(src)
        if not result:
            return "", src  # the src is a pure id
        path_name = result[0][0]  # at most one path_name
        _, ids = src.rsplit(path_name, 1)
        return path_name, ids[len(ID_SEP_KEY) :] if ids.startswith(ID_SEP_KEY) else ""

    @classmethod
    def resolve_relative_ids(cls, id: str, value: str) -> str:
        """
        To simplify the reference or macro tokens ID in the nested config content, it's available to use
        relative ID name which starts with the `ID_SEP_KEY`, for example, "@#A" means `A` in the same level,
        `@##A` means `A` in the upper level.
        It resolves the relative ids to absolute ids. For example, if the input data is:

        .. code-block:: python

            {
                "A": 1,
                "B": {"key": "@##A", "value1": 2, "value2": "%#value1", "value3": [3, 4, "@#1"]},
            }

        It will resolve `B` to `{"key": "@A", "value1": 2, "value2": "%B#value1", "value3": [3, 4, "@B#value3#1"]}`.

        Args:
            id: id name for current config item to compute relative id.
            value: input value to resolve relative ids.
        """
        # get the prefixes like: "@####", "%###", "@#"
        value = ReferenceResolver.normalize_id(value)
        prefixes = sorted(set().union(cls.relative_id_prefix.findall(value)), reverse=True)
        current_id = id.split(ID_SEP_KEY)

        for p in prefixes:
            sym = ID_REF_KEY if ID_REF_KEY in p else MACRO_KEY
            length = p[len(sym) :].count(ID_SEP_KEY)
            if length > len(current_id):
                raise ValueError(f"the relative id in `{value}` is out of the range of config content.")
            if length == len(current_id):
                new = ""  # root id is `""`
            else:
                new = ID_SEP_KEY.join(current_id[:-length]) + ID_SEP_KEY
            value = value.replace(p, sym + new)
        return value
