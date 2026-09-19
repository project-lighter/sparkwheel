"""Disabled component guards prune unneeded runtime dependencies."""

from dataclasses import dataclass

import pytest

from sparkwheel import Component, Config, Expression


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("path", ["off", ""])
def test_static_disabled_component_prunes_runtime_payload(scoped, path):
    calls = []
    source = {
        "off": {
            "_target_": lambda **kwargs: calls.append("target"),
            "_disabled_": True,
            "bad": "$1 / 0",
            "missing": "@missing",
            "nested": {"_target_": lambda: calls.append("nested")},
            "setup": "$import nonexistent_disabled_payload",
        }
    }
    config = Config(data=source)
    resolver = config.retain().scope() if scoped else config
    assert resolver.resolve(path) == (None if path else {})
    assert calls == []


@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("scoped", [False, True])
def test_dynamic_guard_resolves_only_needed_dependencies_before_payload(disabled, scoped):
    calls = []

    def guard():
        calls.append("guard")
        return disabled

    config = Config(
        data={
            "off": {"_target_": lambda n: calls.append("target") or n, "_disabled_": "$guard()", "n": "$payload()"},
        },
        imports={"guard": guard, "payload": lambda: calls.append("payload") or 2},
    )
    resolver = config.retain().scope() if scoped else config
    assert resolver.resolve("off") == (None if disabled else 2)
    assert calls == (["guard"] if disabled else ["guard", "payload", "target"])
    resolver.resolve("off")
    assert calls.count("guard") == 1


@pytest.mark.parametrize("scoped", [False, True])
def test_disabled_parent_does_not_prevent_explicit_child_request(scoped):
    config = Config(
        data={
            "off": {
                "_target_": "builtins.dict",
                "_disabled_": True,
                "child": {
                    "_target_": "builtins.dict",
                    "value": "$m.sqrt(4)",
                    "setup": "$import math as m",
                },
            }
        }
    )
    resolver = config.retain().scope() if scoped else config
    assert resolver.resolve("off") is None
    assert resolver.resolve("off::child")["value"] == 2


def test_disabled_mode_controls_do_not_execute_guard_expressions_when_disabled():
    calls = []
    config = Config(
        data={
            "off": {
                "_target_": lambda n: calls.append("target"),
                "_disabled_": "$guard()",
                "n": "$payload()",
            }
        },
        imports={"guard": lambda: calls.append("guard") or True, "payload": lambda: calls.append("payload")},
    )
    deferred = config.resolve("off", eval_expr=False)
    assert isinstance(deferred, Component)
    assert isinstance(deferred.get_config()["_disabled_"], Expression)
    assert calls == []
    assert config.resolve("off") is None
    assert calls == ["guard"]
    assert config.resolve("off", eval_expr=False) is deferred


def test_static_disabled_scoped_node_prunes_blocked_payload_without_effects():
    config = Config(data={"off": {"_target_": "builtins.dict", "_disabled_": True, "payload": "$1 / 0"}})
    scope = config.retain().scope(blocked_paths={"off::payload"})
    assert scope.resolve("off") is None
    assert scope.materialized_components() == {}


def test_disabled_component_does_not_validate_unresolved_constructor_arguments():
    @dataclass
    class Args:
        n: int

    config = Config(schema=Args).update({"_target_": "builtins.dict", "_disabled_": True, "n": "$'invalid'"})
    assert config.resolve() is None


@pytest.mark.parametrize("scoped", [False, True])
def test_dynamic_true_guard_suppresses_payload_imports_but_guard_imports_execute(scoped):
    config = Config(
        data={
            "off": {
                "_target_": "missing.Target",
                "_disabled_": "$import math; math.isfinite(2)",
                "setup": "$import missing_disabled_payload_import",
                "value": "$1 / 0",
            }
        }
    )
    resolver = config.retain().scope() if scoped else config
    assert resolver.resolve("off") is None


@pytest.mark.parametrize("scoped", [False, True])
def test_guard_can_reference_an_import_prefixed_dependency(scoped):
    config = Config(
        data={
            "flag": "$import math; math.isfinite(2)",
            "off": {"_target_": "missing.Target", "_disabled_": "@flag", "value": "$1 / 0"},
        }
    )
    resolver = config.retain().scope() if scoped else config
    assert resolver.resolve("off") is None
    assert resolver.resolve("flag") is True


def test_dynamic_scoped_guard_does_not_bypass_conservative_block_preflight():
    calls = []
    config = Config(
        data={
            "off": {
                "_target_": "builtins.dict",
                "_disabled_": "$guard()",
                "payload": "$1 / 0",
            }
        },
        imports={"guard": lambda: calls.append("guard") or True},
    )
    scope = config.retain().scope(blocked_paths={"off::payload"})
    with pytest.raises(ValueError, match="blocked"):
        scope.resolve("off")
    assert calls == []


def test_static_disabled_root_scan_keeps_copied_descendant_available_for_explicit_scope_request():
    config = Config(
        data={
            "template": {"n": 3},
            "off": {"_target_": "builtins.dict", "_disabled_": True, "child": "%template"},
        }
    )
    scope = config.retain().scope()
    assert scope.resolve() == {"template": {"n": 3}}
    assert scope.resolve("off::child") == {"n": 3}


def test_false_literal_guard_constructs_normally_and_unevaluated_static_guard_keeps_identity():
    config = Config(
        data={
            "on": {"_target_": "builtins.dict", "_disabled_": False, "n": "$2"},
            "off": {"_target_": "builtins.dict", "_disabled_": True, "n": "$1 / 0"},
        }
    )
    assert config.resolve("on") == {"n": 2}
    wrapper = config.resolve("off", instantiate=False)
    assert isinstance(wrapper, Component)
    assert wrapper.get_config()["n"] == "$1 / 0"
    assert config.resolve("off", instantiate=False) is wrapper
    assert config.resolve("off") is None


def test_circular_disabled_guard_fails_before_payload_construction():
    from sparkwheel import CircularReferenceError

    calls = []
    config = Config(data={"off": {"_target_": lambda: calls.append("target"), "_disabled_": "$bool(@off)"}})
    with pytest.raises(CircularReferenceError):
        config.resolve("off")
    assert calls == []


@pytest.mark.parametrize("guard", [True, "$guard()"])
def test_schema_variant_discriminator_is_not_evaluated_for_disabled_payload(guard):
    from typing import Literal

    @dataclass
    class IntegerArgs:
        kind: Literal["int"]
        n: int

    @dataclass
    class FloatArgs:
        kind: Literal["float"]
        n: float

    @dataclass
    class Root:
        choice: IntegerArgs | FloatArgs

    calls = []
    config = Config(
        schema=Root,
        imports={
            "guard": lambda: calls.append("guard") or True,
            "kind": lambda: calls.append("kind") or "int",
        },
    ).update({"choice": {"_target_": "builtins.dict", "_disabled_": guard, "kind": "$kind()", "n": "$1 / 0"}})
    assert config.resolve("choice") is None
    assert calls == ([] if guard is True else ["guard"])


def test_exact_guard_bindings_override_source_before_static_pruning():
    recipe = Config(
        data={"off": {"_target_": "builtins.dict", "_disabled_": True, "n": "$m.sqrt(4)", "setup": "$import math as m"}}
    ).retain()
    enabled = recipe.scope(bindings={"off::_disabled_": False})
    assert enabled.resolve("off")["n"] == 2

    recipe = Config(data={"off": {"_target_": "builtins.dict", "_disabled_": False, "n": "$1 / 0"}}).retain()
    disabled = recipe.scope(bindings={"off::_disabled_": True}, blocked_paths={"off::n"})
    assert disabled.resolve("off") is None


def test_blocked_guard_is_checked_even_when_source_guard_is_statically_true():
    recipe = Config(data={"off": {"_target_": "builtins.dict", "_disabled_": True}}).retain()
    with pytest.raises(ValueError, match="blocked"):
        recipe.scope(blocked_paths={"off::_disabled_"}).resolve("off")


def test_late_guard_rebinding_cannot_change_an_already_consumed_disabled_decision():
    scope = Config(data={"off": {"_target_": "builtins.dict", "_disabled_": True}}).retain().scope()
    assert scope.resolve("off") is None
    with pytest.raises(ValueError, match="fresh scope"):
        scope.bind("off::_disabled_", False)
    scope.bind("off::_disabled_", True)
