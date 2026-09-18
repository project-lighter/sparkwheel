"""Behavioral contracts for retained recipes and isolated construction scopes."""

import pytest

from sparkwheel import Config, ConfigKeyError


def test_retaining_and_creating_scope_do_not_import_or_construct(monkeypatch):
    import sparkwheel.config as config_module

    def forbidden(*args, **kwargs):
        raise AssertionError("Creation executed Python")

    monkeypatch.setattr(config_module, "optional_import", forbidden)
    config = Config(data={"_imports_": {"missing": "missing_package"}, "object": {"_target_": forbidden}})
    recipe = config.retain()
    scope = recipe.scope()
    assert scope.materialized_components() == {}


def test_bound_recipe_and_dependencies_are_suppressed_in_ancestor_scan():
    calls = []

    def forbidden(**kwargs):
        calls.append(kwargs)
        raise AssertionError("Bound recipe was executed")

    config = Config(
        data={
            "object": {"_target_": forbidden, "dependency": {"_target_": forbidden}},
            "alias": "@object",
        }
    )
    existing = object()
    scope = config.retain().scope(bindings={"object": existing})
    result = scope.resolve()
    assert result["object"] is existing
    assert result["alias"] is existing
    assert scope.materialized_components() == {}
    assert calls == []


def test_bound_recipe_prunes_broken_raw_references():
    existing = object()
    scope = (
        Config(data={"object": {"_target_": "builtins.dict", "bad": "%missing"}}).retain().scope(bindings={"object": existing})
    )
    assert scope.resolve()["object"] is existing


@pytest.mark.parametrize("path", ["", "late", "late::dependency", "alias"])
def test_blocked_graph_fails_before_import_or_dependency_effects(path, monkeypatch):
    import sparkwheel.config as config_module

    calls = []

    def side_effect():
        calls.append("constructor")
        return object()

    def import_effect(*args, **kwargs):
        calls.append("import")
        raise AssertionError("Import must wait for preflight")

    monkeypatch.setattr(config_module, "optional_import", import_effect)
    scope = (
        Config(
            data={
                "_imports_": {"library": "missing_package"},
                "early": {"_target_": side_effect},
                "late": {"_target_": "builtins.dict", "dependency": {"_target_": side_effect}},
                "alias": "@late",
            }
        )
        .retain()
        .scope(blocked_paths={"late"})
    )
    with pytest.raises(ValueError, match="late"):
        scope.resolve(path)
    assert calls == []


def test_blocked_plain_child_is_checked_before_ancestor_construction():
    calls = []
    scope = (
        Config(data={"object": {"_target_": lambda **kwargs: calls.append(kwargs), "value": 1}})
        .retain()
        .scope(blocked_paths={"object::value"})
    )
    with pytest.raises(ValueError, match="object::value"):
        scope.resolve("object")
    assert calls == []


def test_bound_parent_with_blocked_descendant_and_exact_child_binding():
    config = Config(data={"model": {"network": {"_target_": "builtins.dict"}, "optimizer": 1}, "alias": "@model"})
    model, network = object(), object()
    scope = config.retain().scope(bindings={"model": model, "model::network": network}, blocked_paths={"model::optimizer"})
    assert scope.resolve("model") is model
    assert scope.resolve("model::network") is network
    assert scope.resolve("alias") is model
    with pytest.raises(ValueError, match="optimizer"):
        scope.resolve("model::optimizer")


def test_scope_iterator_caches_are_fresh_and_aliases_share():
    recipe = Config(data={"iterator": "$iter([1, 2])", "alias": "@iterator"}).retain()
    first, second = recipe.scope(), recipe.scope()
    iterator = first.resolve("iterator")
    assert first.resolve("alias") is iterator
    assert list(iterator) == [1, 2]
    assert list(first.resolve("iterator")) == []
    assert list(second.resolve("iterator")) == [1, 2]
    assert first.materialized_components() == {}


def test_retained_source_is_independent_of_edits_and_runtime_cache():
    config = Config(data={"value": 2, "object": {"_target_": "builtins.dict", "value": "%value"}})
    old_runtime = config.resolve("object")
    recipe = config.retain()
    config.set("value", 7)
    first, second = recipe.scope(), recipe.scope()
    assert first.resolve("object") == {"value": 2}
    assert first.resolve("object") is not old_runtime
    assert first.resolve("object") is not second.resolve("object")
    assert config.get("object::value") == "%value"


def test_same_identity_bind_is_allowed_but_rebinding_is_rejected():
    scope = Config(data={"object": {"_target_": "builtins.dict"}}).retain().scope()
    value = scope.resolve("object")
    scope.bind("object", value)
    scope.bind("object", value)
    with pytest.raises(ValueError, match="object"):
        scope.bind("object", {})
    assert scope.resolve("object") is value


def test_unresolved_binding_works_and_never_enters_materialized_map():
    scope = Config(data={"object": {"_target_": "builtins.dict"}, "alias": "@object"}).retain().scope()
    value = object()
    scope.bind("object", value)
    assert scope.resolve("alias") is value
    assert scope.materialized_components() == {}


@pytest.mark.parametrize("kind", ["binding", "block"])
def test_invalid_declaration_paths_are_rejected(kind):
    recipe = Config(data={"object": 1}).retain()
    with pytest.raises(ConfigKeyError, match="typo"):
        recipe.scope(**({"bindings": {"typo": 2}} if kind == "binding" else {"blocked_paths": {"typo"}}))


def test_local_copy_child_is_a_valid_binding_path():
    source = {"template": {"child": {"_target_": "builtins.dict"}}, "copy": "%template"}
    existing = object()
    scope = Config(data=source).retain().scope(bindings={"copy::child": existing})
    assert scope.resolve("copy")["child"] is existing
    assert scope.resolve("template")["child"] is not existing


def test_binding_under_blocked_ancestor_is_rejected():
    recipe = Config(data={"object": {"child": 1}}).retain()
    with pytest.raises(ValueError, match="object"):
        recipe.scope(bindings={"object::child": 2}, blocked_paths={"object"})


def test_materialized_map_only_reports_constructed_components_and_is_defensive():
    scope = (
        Config(
            data={
                "object": {"_target_": "builtins.dict", "child": {"_target_": "builtins.list"}},
                "iterator": "$iter([1, 2])",
                "alias": "@object",
                "disabled": {"_target_": "builtins.dict", "_disabled_": True},
            }
        )
        .retain()
        .scope()
    )
    result = scope.resolve()
    components = scope.materialized_components()
    assert components == {"object": result["object"], "object::child": result["object"]["child"]}
    assert components["object"] is result["alias"]
    components.clear()
    assert set(scope.materialized_components()) == {"object", "object::child"}


def test_scopes_get_fresh_import_namespaces_without_losing_caller_bindings():
    import math

    recipe = Config(data={"_imports_": {"j": "json"}, "value": "$j.dumps(m.sqrt(4))"}, imports={"m": math}).retain()
    assert recipe.scope().resolve("value") == "2.0"
    assert recipe.scope().resolve("value") == "2.0"


def test_bound_parent_keeps_unbound_descendant_recipe_resolvable():
    network = object()
    model = object()
    scope = (
        Config(
            data={
                "model": {
                    "network": {"_target_": "builtins.dict"},
                    "optimizer": {"_target_": "builtins.dict", "params": "@model::network"},
                },
            }
        )
        .retain()
        .scope(bindings={"model": model, "model::network": network})
    )
    assert scope.resolve("model") is model
    assert scope.resolve("model::optimizer")["params"] is network
    assert set(scope.materialized_components()) == {"model::optimizer"}


def test_late_binding_cannot_make_cached_ancestor_inconsistent():
    scope = Config(data={"container": {"plain": []}}).retain().scope()
    container = scope.resolve("container")
    with pytest.raises(ValueError, match="fresh scope"):
        scope.bind("container::plain", [])
    scope.bind("container::plain", container["plain"])
    assert scope.resolve("container::plain") is container["plain"]


def test_bound_parent_suppresses_unrelated_broken_sibling_when_resolving_child():
    scope = (
        Config(data={"model": {"bad": "%missing", "optimizer": {"_target_": "builtins.dict"}}})
        .retain()
        .scope(bindings={"model": object()})
    )
    assert scope.resolve("model::optimizer") == {}


def test_bound_direct_resolution_does_not_import(monkeypatch):
    import sparkwheel.config as config_module

    def forbidden(*args, **kwargs):
        raise AssertionError("Bound-only resolution imported Python")

    monkeypatch.setattr(config_module, "optional_import", forbidden)
    existing = object()
    scope = (
        Config(data={"_imports_": {"lib": "missing"}, "object": {"_target_": "builtins.dict"}})
        .retain()
        .scope(bindings={"object": existing})
    )
    assert scope.resolve("object") is existing


def test_no_boundary_scope_matches_config_for_nested_copies_relative_refs_and_imports():
    from copy import deepcopy

    source = {
        "_imports_": {"m": "math"},
        "setup": "$import json as j",
        "n": 9,
        "template": {"n": 4, "number": "%::n", "alias": "@::n", "object": {"_target_": "builtins.list"}},
        "copy": "%template",
        "second_copy": "%copy",
        "same": "@copy::object",
        "expression": "$j.dumps(m.sqrt(@n))",
    }
    config = Config(data=deepcopy(source))
    expected = config.resolve()
    scope = Config(data=deepcopy(source)).retain().scope()
    actual = scope.resolve()
    assert actual == expected
    assert actual["same"] is actual["copy"]["object"]
    assert actual["template"]["object"] is not actual["copy"]["object"]
    assert actual["second_copy"]["object"] is not actual["copy"]["object"]


def test_constructed_error_keeps_retained_source_location(tmp_path):
    from sparkwheel import InstantiationError

    path = tmp_path / "recipe.yaml"
    path.write_text("object:\n  _target_: builtins.int\n  _args_: [not-an-integer]\n")
    config = Config().update(path)
    recipe = config.retain()
    config._locations._locations.clear()
    with pytest.raises(InstantiationError) as error:
        recipe.scope().resolve("object")
    assert error.value.source_location.filepath == str(path)
    assert error.value.source_location.line == 2


@pytest.mark.parametrize("path", ["items::-1", "items::00"])
def test_noncanonical_list_binding_paths_are_rejected(path):
    recipe = Config(data={"items": [1]}).retain()
    with pytest.raises(ConfigKeyError, match="Unknown construction path"):
        recipe.scope(bindings={path: object()})


def test_list_binding_is_authoritative_when_resolving_ancestor():
    existing = object()
    scope = Config(data={"items": [{"_target_": "builtins.dict"}]}).retain().scope(bindings={"items::0": existing})
    assert scope.resolve("items")[0] is existing
    assert scope.materialized_components() == {}


def test_import_expression_inside_explicit_descendant_of_bound_parent_runs_first():
    source = {
        "model": {
            "optimizer": {
                "_target_": "builtins.dict",
                "value": "$m.sqrt(4)",
                "setup": "$import math as m",
            }
        }
    }
    scope = Config(data=source).retain().scope(bindings={"model": object()})
    assert scope.resolve("model::optimizer") == Config(data=source).resolve("model::optimizer")


def test_materialized_components_excludes_component_returned_iterators():
    scope = Config(data={"iterator": {"_target_": "builtins.iter", "_args_": [[1, 2]]}}).retain().scope()
    assert list(scope.resolve("iterator")) == [1, 2]
    assert scope.materialized_components() == {}
