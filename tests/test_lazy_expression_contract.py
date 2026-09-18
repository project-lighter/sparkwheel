from dataclasses import dataclass
from typing import Any

import pytest

from sparkwheel import Config
from sparkwheel.items import Expression
from sparkwheel.schema import ValidationError
from sparkwheel.utils.exceptions import CircularReferenceError


@pytest.mark.parametrize(
    "expression", ["$@safe if True else @bad", "$True or @bad", "$False and @bad", "$[@safe for _ in range(1)]"]
)
def test_native_selection(expression):
    config = Config({"safe": 2, "bad": "$1/0", "selected": expression})
    result = config.resolve("selected")
    assert result in (2, True, False, [2])
    assert "bad" not in config._resolver._resolved


def test_selected_dependency_executes_once_and_shares_identity():
    calls = []

    def create():
        calls.append(1)
        return object()

    config = Config({"good": {"_target_": create}, "bad": "$1/0", "selected": "$@good if True else @bad"})
    result = config.resolve("selected")
    assert result is config.resolve("selected") is config.resolve("good")
    assert calls == [1]


def test_evaluated_cycle_has_error_cause():
    config = Config({"a": "$@b", "b": "$@a"})
    with pytest.raises(CircularReferenceError):
        config.resolve("a")


def test_missing_unselected_reference_is_unused():
    assert Config({"x": "$1 if True else @missing"}).resolve("x") == 1


def test_schema_boundary_still_rejects_before_constructor():
    @dataclass
    class Root:
        value: int

    calls = []

    def create(value):
        calls.append(value)
        return object()

    config = Config(schema=Root).update({"_target_": create, "value": "$'bad' if True else @missing"})
    with pytest.raises(ValidationError):
        config.resolve()
    assert not calls


def test_schema_coercion_and_shared_alias():
    @dataclass
    class Root:
        n: int
        alias: int
        unused: Any

    config = Config(schema=Root, coerce=True).update({"n": "$'2' if True else @unused", "alias": "@n", "unused": "$1/0"})
    assert config.resolve("n") == config.resolve("alias") == 2


def test_retained_scope_lazy_runtime_preserves_static_blocks():
    recipe = Config({"safe": 2, "bad": "$1/0", "selected": "$@safe if True else @bad"}).retain()
    assert recipe.scope().resolve("selected") == 2
    with pytest.raises(ValueError, match="blocked"):
        recipe.scope(blocked_paths={"bad"}).resolve("selected")


def test_modes_remain_distinct():
    config = Config({"n": 2, "x": "$@n + 1"})
    unevaluated = config.resolve("x", eval_expr=False)
    assert isinstance(unevaluated, Expression)
    assert config.resolve("x") == 3
    assert config.resolve("x", eval_expr=False) is unevaluated


def test_old_delayed_callable_keeps_prior_generation():
    config = Config({"n": 1, "f": "$lambda: @n"})
    old = config.resolve("f")
    config.set("n", 2)
    new = config.resolve("f")
    assert old() == 1
    assert new() == 2


def test_scope_delayed_callable_cannot_change_under_late_binding():
    scope = Config({"n": [1], "f": "$lambda: @n"}).retain().scope()
    delayed = scope.resolve("f")
    with pytest.raises(ValueError, match="after use"):
        scope.bind("n", [2])
    assert delayed() == [1]


def test_old_delayed_generator_keeps_prior_generation():
    config = Config({"n": 1, "g": "$( @n for _ in range(2))"})
    old = config.resolve("g")
    config.update({"n": 2})
    new = config.resolve("g")
    assert list(old) == [1, 1]
    assert list(new) == [2, 2]


def test_late_same_identity_binding_remains_valid():
    scope = Config({"n": [1], "f": "$lambda: @n"}).retain().scope()
    delayed = scope.resolve("f")
    value = scope.resolve("n")
    scope.bind("n", value)
    assert delayed() is value


def test_schema_delayed_generation_keeps_old_value_and_cache():
    @dataclass
    class Root:
        n: int
        f: Any

    config = Config(schema=Root, coerce=True).update({"n": "$'1'", "f": "$lambda: @n"})
    old = config.resolve("f")
    config.update({"n": "$'2'"})
    new = config.resolve("f")
    assert old() == 1
    assert new() == 2


def test_scope_unselected_reference_binding_is_conservatively_reserved():
    scope = Config({"a": 1, "b": 2, "x": "$@a if True else @b"}).retain().scope()
    assert scope.resolve("x") == 1
    with pytest.raises(ValueError, match="after use"):
        scope.bind("b", 3)
    assert scope.resolve("b") == 2


@pytest.mark.parametrize("kind", ["lambda: @n", "(@n for _ in range(2))"])
def test_rejected_edit_preserves_delayed_value_generation(kind):
    @dataclass
    class Root:
        n: int
        delayed: Any

    config = Config(schema=Root).update({"n": 1, "delayed": "$" + kind})
    old = config.resolve("delayed")
    resolver = config._resolver
    with pytest.raises(ValidationError):
        config.update({"n": "invalid"})
    assert config._resolver is resolver
    assert config.resolve("delayed") is old
    assert (old() if callable(old) else list(old)) in (1, [1, 1])


def test_delayed_import_namespace_is_owned_by_generation():
    config = Config({"_imports_": {"ops": "math"}, "n": 4, "f": "$lambda: ops.sqrt(@n)"})
    old = config.resolve("f")
    config.update({"_imports_": {"ops": "cmath"}, "n": 9})
    new = config.resolve("f")
    assert old() == 2.0 and type(old()) is float
    assert new() == 3.0 and type(new()) is complex


@pytest.mark.parametrize("order", [(False, True), (True, False)])
def test_delayed_references_keep_instantiation_mode_identity(order):
    from sparkwheel.items import Component

    calls = []

    def create():
        calls.append(1)
        return object()

    config = Config({"object": {"_target_": create}, "callback": "$lambda: @object"})
    callbacks = {mode: config.resolve("callback", instantiate=mode) for mode in order}
    assert calls == []
    native = callbacks[True]()
    wrapper = callbacks[False]()
    assert calls == [1]
    assert isinstance(wrapper, Component)
    assert callbacks[True]() is config.resolve("object") is native
    assert callbacks[False]() is config.resolve("object", instantiate=False) is wrapper


def test_forced_rebuild_does_not_reset_a_published_callback():
    calls = []

    def create():
        obj = object()
        calls.append(obj)
        return obj

    config = Config({"object": {"_target_": create}, "callback": "$lambda: @object"})
    old = config.resolve("callback")
    new = config.resolve("callback", lazy=False)
    assert old is not new
    assert old() is not new()
    assert old() is calls[0]
    assert new() is calls[1]
    assert len(calls) == 2


def test_schema_error_in_old_callback_keeps_original_file_location(tmp_path):
    @dataclass
    class Root:
        n: int
        callback: Any

    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text("n: \"$'invalid'\"\ncallback: '$lambda: @n'\n")
    second.write_text("n: '$2'\n")
    config = Config(schema=Root).update(first)
    old = config.resolve("callback")
    config.update(second)
    assert config.resolve("callback")() == 2
    with pytest.raises(ValidationError) as caught:
        old()
    assert caught.value.source_location.filepath == str(first)


def test_reservation_covers_nested_changes_and_same_identity_bindings():
    source = {"group": {"n": [1]}, "callback": "$lambda: @group"}
    scope = Config(source).retain().scope()
    callback = scope.resolve("callback")
    with pytest.raises(ValueError, match="fresh scope"):
        scope.bind("group::n", [2])
    group = scope.resolve("group")
    scope.bind("group", group)
    assert callback() is group


def test_unselected_cycle_does_not_execute_in_ordinary_config():
    config = Config({"result": "$1 if True else @result"})
    assert config.resolve("result") == 1
    # Scopes retain their conservative static graph contract.
    with pytest.raises(CircularReferenceError):
        config.retain().scope().resolve("result")


@pytest.mark.parametrize("first", ["a", "b"])
def test_published_callback_cycle_is_detected_in_either_order(first):
    config = Config({"a": "$lambda: @b", "b": "$@a()"})
    if first == "a":
        config.resolve("a")
    with pytest.raises(CircularReferenceError):
        config.resolve("b")
    assert not any(config._resolver._active_resolutions.values())


def test_published_callback_detects_active_constructor_cycle():
    from sparkwheel.utils.exceptions import InstantiationError

    def create(callback):
        return callback()

    config = Config({"a": "$lambda: @b", "b": {"_target_": create, "callback": "@a"}})
    config.resolve("a")
    with pytest.raises(InstantiationError) as caught:
        config.resolve("b")
    cause = caught.value.__cause__
    while isinstance(cause, InstantiationError):
        cause = cause.__cause__
    assert isinstance(cause, CircularReferenceError)
    assert not any(config._resolver._active_resolutions.values())


def test_cached_callback_can_recurse_with_ordinary_python_termination():
    config = Config({"a": "$lambda n: 0 if n <= 0 else @a(n - 1) + 1"})
    callback = config.resolve("a")
    assert callback(4) == 4
    assert config.resolve("a") is callback


def test_failed_expression_clears_active_state_for_retry():
    attempts = []

    def sometimes():
        attempts.append(1)
        if len(attempts) == 1:
            raise ValueError("try again")
        return 3

    from sparkwheel.utils.exceptions import EvaluationError

    config = Config({"result": "$sometimes()"}, imports={"sometimes": sometimes})
    with pytest.raises(EvaluationError):
        config.resolve("result")
    assert config.resolve("result") == 3
    assert len(attempts) == 2
    assert not any(config._resolver._active_resolutions.values())
