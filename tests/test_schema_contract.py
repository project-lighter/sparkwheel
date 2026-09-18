"""Schema policy checks across edits and value/constructor boundaries."""

from dataclasses import dataclass, field
from typing import Literal

import pytest

from sparkwheel import MISSING, Config, ValidationError, validate, validator


@dataclass
class ChoiceA:
    kind: Literal["a"]
    count: int


@dataclass
class ChoiceB:
    kind: Literal["b"]
    count: int


@dataclass
class ChoiceContainer:
    choice: ChoiceA | ChoiceB | None


def test_optional_discriminated_union_accepts_none():
    validate({"choice": None}, ChoiceContainer)


def test_nested_missing_and_leniency_propagate_to_selected_union_branch():
    validate({"choice": {"kind": "a", "count": MISSING, "extra": 1}}, ChoiceContainer, allow_missing=True, strict=False)


def test_postponed_annotations_resolve_with_module_context(monkeypatch):
    import sys
    import types

    module = types.ModuleType("_test_sparkwheel_schema_annotations")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(
        "from __future__ import annotations\nfrom dataclasses import dataclass\n@dataclass\nclass Child:\n    n: int\n@dataclass\nclass Parent:\n    child: Child\n",
        module.__dict__,
    )
    validate({"child": {"n": 2}}, module.Parent)
    with pytest.raises(ValidationError):
        validate({"child": {"n": "invalid"}}, module.Parent)


def test_framework_keys_do_not_suppress_custom_validator():
    @dataclass
    class Positive:
        n: int

        @validator
        def check_positive(self):
            if self.n <= 0:
                raise ValueError("n must be positive")

    with pytest.raises(ValidationError, match="n must be positive"):
        Config(schema=Positive).update({"_target_": "builtins.dict", "n": -1})


def test_validator_setup_failure_preserves_original_cause():
    @dataclass
    class BadSetup:
        n: int

        def __post_init__(self):
            raise RuntimeError("setup failed")

        @validator
        def check_n(self):
            raise AssertionError("unreachable")

    with pytest.raises(ValidationError, match="setup failed") as error:
        validate({"n": 2}, BadSetup)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_defaults_are_not_inserted_and_factories_are_not_called_for_type_validation():
    calls = []

    @dataclass
    class Defaults:
        n: int = 2
        values: list = field(default_factory=lambda: calls.append("default") or [])

    config = Config(schema=Defaults).update({})
    assert config.get() == {}
    assert calls == []


@pytest.mark.parametrize("annotation", [int, float, Literal[1]])
def test_bool_does_not_pass_as_a_numeric_field(annotation):
    @dataclass
    class Numeric:
        n: annotation

    with pytest.raises(ValidationError):
        validate({"n": True}, Numeric)


@dataclass
class Coercible:
    count: int
    ratio: float
    enabled: bool
    numbers: list[int]


def test_schema_coercion_applies_to_staged_source_recursively():
    config = Config(schema=Coercible).update({"count": "2", "ratio": "0.5", "enabled": "false", "numbers": ["1", "3"]})
    assert config.get() == {"count": 2, "ratio": 0.5, "enabled": False, "numbers": [1, 3]}
    config.set("count", "4")
    assert config.get("count") == 4


def test_disabled_coercion_rejects_strings_transactionally():
    config = Config(schema=Coercible, coerce=False).update({"count": 2, "ratio": 0.5, "enabled": False, "numbers": [1]})
    before = config.get()
    with pytest.raises(ValidationError):
        config.set("count", "4")
    assert config.get() is before


@pytest.mark.parametrize("value", [2.5, True, [1, 2]])
def test_coercion_does_not_truncate_or_reinterpret_unrelated_types(value):
    @dataclass
    class Counter:
        n: int

    with pytest.raises(ValidationError):
        Config(schema=Counter).update({"n": value})


def test_ambiguous_union_coercion_is_rejected_but_existing_string_branch_wins():
    @dataclass
    class Ambiguous:
        n: int | float

    with pytest.raises(ValidationError, match="Ambiguous"):
        Config(schema=Ambiguous).update({"n": "2"})

    @dataclass
    class StringOrInt:
        n: int | str

    config = Config(schema=StringOrInt).update({"n": "002"})
    assert config.get("n") == "002"


@dataclass
class CountArgs:
    n: int


@dataclass
class NestedArgs:
    child: CountArgs
    label: str


@dataclass
class RuntimeConfig:
    model: NestedArgs
    untouched: CountArgs


def test_resolved_invalid_argument_fails_before_target_constructor():
    calls = []
    config = Config(schema=CountArgs).update({"_target_": lambda n: calls.append(n), "n": "$'invalid'"})
    with pytest.raises(ValidationError, match="n"):
        config.resolve()
    assert calls == []
    assert config.get("n") == "$'invalid'"


def test_resolved_argument_coercion_keeps_native_children_and_unrelated_nodes_unbuilt():
    calls = []

    class Child:
        def __init__(self, n):
            calls.append(("child", n))
            self.n = n

    class Parent:
        def __init__(self, child, label):
            calls.append(("parent", label))
            assert isinstance(child, Child)
            self.child = child

    config = Config(schema=RuntimeConfig).update(
        {
            "model": {"_target_": Parent, "child": {"_target_": Child, "n": "$'7'"}, "label": "native"},
            "untouched": {"_target_": lambda n: calls.append(("untouched", n)), "n": 1},
        }
    )
    model = config.resolve("model")
    assert model.child.n == 7
    assert calls == [("child", 7), ("parent", "native")]
    assert config.resolve("model") is model
    assert config.resolve("model::child") is model.child
    assert config.get("model::child::n") == "$'7'"


def test_runtime_coercion_disabled_rejects_expression_result():
    config = Config(schema=CountArgs, coerce=False).update({"n": "$'2'"})
    with pytest.raises(ValidationError):
        config.resolve("n")


def test_root_validator_runs_only_on_root_resolution_with_resolved_arguments():
    calls = []

    @dataclass
    class Bounds:
        start: int
        end: int

        @validator
        def ascending(self):
            calls.append((self.start, self.end))
            if self.start >= self.end:
                raise ValueError("bounds must ascend")

    config = Config(schema=Bounds).update({"start": "$5", "end": "$1"})
    assert calls == []
    assert config.resolve("start") == 5
    assert calls == []
    with pytest.raises(ValidationError, match="bounds must ascend"):
        config.resolve()
    assert calls == [(5, 1)]


def test_component_aliases_validate_definition_arguments_without_reconstructing():
    @dataclass
    class Aliased:
        first: CountArgs
        second: CountArgs

    calls = []
    config = Config(schema=Aliased).update(
        {
            "first": {"_target_": lambda n: calls.append(n) or object(), "n": "$2"},
            "second": "@first",
        }
    )
    values = config.resolve()
    assert values["first"] is values["second"]
    assert calls == [2]


def test_attached_schema_cannot_silently_disappear_in_retained_scope():
    config = Config(schema=CountArgs).update({"n": 1})
    with pytest.raises(NotImplementedError, match="schema"):
        config.retain()


def test_native_container_component_identity_survives_parent_and_alias_coercion():
    @dataclass
    class Shared:
        first: CountArgs
        second: CountArgs

    config = Config(schema=Shared).update(
        {
            "first": {"_target_": "builtins.dict", "n": "$'2'"},
            "second": "@first",
        }
    )
    first = config.resolve("first")
    values = config.resolve()
    assert first == {"n": 2}
    assert values["first"] is first
    assert values["second"] is first
    assert config.resolve("second") is first


def test_alias_cannot_claim_coerced_arguments_after_component_was_constructed():
    @dataclass
    class TextArgs:
        n: str

    @dataclass
    class Conflicting:
        first: TextArgs
        second: CountArgs

    config = Config(schema=Conflicting).update(
        {
            "first": {"_target_": "builtins.dict", "n": "2"},
            "second": "@first",
        }
    )
    assert config.resolve("first") == {"n": "2"}
    with pytest.raises(ValidationError):
        config.resolve("second")


def test_unexpected_validator_exception_is_not_swallowed_by_union_fallback():
    @dataclass
    class Broken:
        n: int

        @validator
        def check(self):
            raise RuntimeError("unexpected validation failure")

    @dataclass
    class Alternative:
        n: int

    @dataclass
    class Root:
        value: Broken | Alternative

    with pytest.raises(ValidationError, match="unexpected validation failure") as error:
        validate({"value": {"n": 1}}, Root)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_overflowing_or_inexact_integer_is_not_coerced_to_float():
    @dataclass
    class Ratio:
        value: float

    for value in (10**400, 2**53 + 1):
        with pytest.raises(ValidationError, match="represented"):
            Config(schema=Ratio).update({"value": value})


@dataclass
class IntChoice:
    kind: Literal["int"]
    n: int


@dataclass
class FloatChoice:
    kind: Literal["float"]
    n: float


@dataclass
class RuntimeChoice:
    choice: IntChoice | FloatChoice | None


@pytest.mark.parametrize("kind", ["int", "$'int'"])
def test_selected_union_child_uses_its_branch_and_constructor_receives_coercion(kind):
    calls = []
    config = Config(schema=RuntimeChoice).update(
        {
            "choice": {"_target_": lambda **kw: calls.append(kw) or kw, "n": "$'2'", "kind": kind},
        }
    )
    result = config.resolve("choice")
    assert result == {"n": 2, "kind": "int"}
    assert type(result["n"]) is int
    assert calls == [result]


def test_local_copy_arguments_coerce_at_runtime_without_rewriting_source_template():
    @dataclass
    class Copy:
        template: dict
        model: CountArgs

    config = Config(schema=Copy).update({"template": {"_target_": "builtins.dict", "n": "2"}, "model": "%template"})
    assert config.resolve("model") == {"n": 2}
    assert config.get("model") == "%template"
    assert config.get("template::n") == "2"


def test_runtime_string_prefix_does_not_suppress_validator():
    @dataclass
    class Text:
        value: str

        @validator
        def check(self):
            if self.value.startswith("$"):
                raise ValueError("prefix is forbidden")

    config = Config(schema=Text).update({"value": "$'$literal'"})
    with pytest.raises(ValidationError, match="prefix is forbidden"):
        config.resolve()


def test_plain_container_references_share_validated_identity():
    @dataclass
    class Shared:
        first: CountArgs
        second: CountArgs

    config = Config(schema=Shared).update({"first": {"n": "$'2'"}, "second": "@first"})
    first = config.resolve("first")
    second = config.resolve("second")
    root = config.resolve()
    assert first is second is root["first"] is root["second"]
    assert first == {"n": 2}


@pytest.mark.parametrize("first_path", ["choice", "choice::n"])
def test_dynamic_discriminator_keeps_child_cache_and_parent_consistent(first_path):
    config = Config(schema=RuntimeChoice).update({"choice": {"n": "$'2'", "kind": "$'float'"}})
    config.resolve(first_path)
    child = config.resolve("choice::n")
    assert type(child) is float
    assert config.resolve("choice")["n"] is child


def test_cached_import_expression_is_checked_on_first_schema_request():
    @dataclass
    class Fields:
        n: int
        other: int

    config = Config(schema=Fields).update({"n": "$import math", "other": 1})
    assert config.resolve("other") == 1
    with pytest.raises(ValidationError):
        config.resolve("n")


def test_discriminated_union_can_also_have_a_primitive_branch():
    @dataclass
    class Mixed:
        choice: IntChoice | FloatChoice | int

    validate({"choice": 2}, Mixed)


def test_circular_discriminator_reference_reports_cycle():
    from sparkwheel import CircularReferenceError

    config = Config(schema=RuntimeChoice).update({"choice": {"n": "$'2'", "kind": "@choice::n"}})
    with pytest.raises(CircularReferenceError, match="Circular"):
        config.resolve("choice::n")


def test_expression_container_is_coerced_before_becoming_a_shared_dependency():
    @dataclass
    class Root:
        args: CountArgs
        alias: CountArgs

    config = Config(schema=Root).update({"args": "$dict(n='2')", "alias": "@args"})
    args = config.resolve("args")
    assert args == {"n": 2}
    assert config.resolve("alias") is args


def test_schema_modes_keep_wrappers_separate_from_runtime_identity():
    from sparkwheel import Component, Expression

    config = Config(schema=CountArgs).update({"_target_": "builtins.dict", "n": "$'2'"})
    wrapper = config.resolve(instantiate=False)
    assert isinstance(wrapper, Component)
    assert wrapper.get_config()["n"] == 2
    runtime = config.resolve()
    assert runtime == {"n": 2}
    deferred = config.resolve(instantiate=False, eval_expr=False)
    assert isinstance(deferred.get_config()["n"], Expression)
    assert config.resolve() is runtime
    assert config.resolve(instantiate=False) is wrapper


def test_direct_retained_recipe_cannot_drop_attached_schema():
    from sparkwheel.construction import RetainedConfig

    with pytest.raises(NotImplementedError, match="schema"):
        RetainedConfig(Config(schema=CountArgs).update({"n": 1}))


def test_discriminated_union_can_also_have_a_plain_mapping_branch():
    @dataclass
    class Mixed:
        choice: IntChoice | FloatChoice | dict[str, int]

    validate({"choice": {"n": 2}}, Mixed)


def test_untagged_union_partial_child_rejects_ambiguous_coercion():
    @dataclass
    class FloatArgs:
        n: float

    @dataclass
    class Root:
        args: CountArgs | FloatArgs

    config = Config(schema=Root).update({"args": {"n": "$'2'"}})
    with pytest.raises(ValidationError, match="Ambiguous"):
        config.resolve("args::n")
