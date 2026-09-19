"""Lexical references and import-prefixed Python expression semantics."""

import math

import pytest

from sparkwheel import Config


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("$'me@example.com'", "me@example.com"),
        ('$"literal @missing and @::relative"', "literal @missing and @::relative"),
        ("$r'@missing\\path'", "@missing\\path"),
        ("$'''literal @missing\n@::relative'''", "literal @missing\n@::relative"),
        ("$f'me@example.com {1 + 1}'", "me@example.com 2"),
        ("$1 # @missing", 1),
    ],
)
def test_python_literal_and_comment_at_characters_are_not_references(expression, expected):
    config = Config(data={"value": expression})
    assert config.resolve("value") == expected
    assert config.retain().scope().resolve("value") == expected
    assert config.get("value") == expression


def test_quoted_reference_lookalike_and_real_reference_coexist():
    config = Config(data={"name": "ok", "group": {"value": "$'@::name=' + @::::name"}})
    assert config.resolve("group::value") == "@::name=ok"


def test_whole_value_references_keep_hyphenated_keys():
    config = Config(data={"learning-rate": 2, "alias": "@learning-rate", "value": "$@alias - 1"})
    assert config.resolve("value") == 1


def test_import_followed_by_expression_returns_final_value():
    config = Config(data={"pi": "$import math; math.pi"})
    assert config.resolve("pi") == math.pi
    assert config.retain().scope().resolve("pi") == math.pi


def test_import_prefix_resolves_reference_dependencies_before_final_expression():
    config = Config(data={"value": "$import math as m; m.sqrt(@n)", "n": 9, "later": "$m.pi"})
    assert config.resolve("value") == 3.0
    assert config.resolve("later") == math.pi
    assert config.retain().scope().resolve("value") == 3.0


def test_all_import_aliases_are_available_and_multiple_import_statements_work():
    config = Config(data={"value": "$from math import sqrt, pi; import json as j; j.dumps(sqrt(4) + pi)"})
    assert config.resolve("value") == str(2 + math.pi)


def test_ordinary_python_matrix_operator_is_not_a_reference():
    class Matrix:
        def __matmul__(self, other):
            return (self, other)

    left, right = Matrix(), Matrix()
    config = Config(data={"value": "$left@right"}, imports={"left": left, "right": right})
    assert config.resolve("value") == (left, right)


def test_import_declarations_are_available_without_executing_unrequested_final_value():
    config = Config(data={"setup": "$import json as j; 1 / 0", "value": "$j.dumps(2)"})
    assert config.resolve("value") == "2"
    assert config.retain().scope().resolve("value") == "2"


def test_dotted_import_uses_python_binding_rules():
    config = Config(data={"value": "$import urllib.parse; urllib.parse.quote('hello world')"})
    assert config.resolve("value") == "hello%20world"


def test_matrix_operator_with_configuration_reference_operands():
    class Matrix:
        def __matmul__(self, other):
            return (self, other)

    left, right = Matrix(), Matrix()
    config = Config(data={"left": left, "right": right, "value": "$@left @ @right"})
    assert config.resolve("value") == (left, right)


def test_import_prefix_and_bare_import_modes_do_not_contaminate_each_other():
    from sparkwheel import Expression

    config = Config(data={"setup": "$import math", "value": "$import math; math.sqrt(@n)", "n": 4})
    deferred = config.resolve("value", eval_expr=False)
    assert isinstance(deferred, Expression)
    assert config.resolve("value") == 2
    assert config.resolve("setup") is math
    assert config.resolve("value", eval_expr=False) is deferred


def test_unsupported_statements_after_import_fail_instead_of_silently_truncating():
    from sparkwheel import EvaluationError

    config = Config(data={"value": "$import math; n = 2; n"})
    with pytest.raises(EvaluationError) as error:
        config.resolve("value")
    assert isinstance(error.value.__cause__, SyntaxError)


def test_reference_string_formatting_uses_normal_python_expression():
    config = Config(data={"n": 2, "value": "$'value={}'.format(@n)"})
    assert config.resolve("value") == "value=2"


def test_fstring_replacement_does_not_add_configuration_reference_syntax():
    from sparkwheel import EvaluationError

    config = Config(data={"n": 2, "value": "$f'value={@n}'"})
    with pytest.raises(EvaluationError) as error:
        config.resolve("value")
    assert isinstance(error.value.__cause__, SyntaxError)


def test_each_import_prefixed_expression_uses_its_own_declared_alias():
    config = Config(data={"real": "$import math as m; m.sqrt(4)", "complex": "$import cmath as m; m.sqrt(4)"})
    assert type(config.resolve("real")) is float
    assert type(config.resolve("complex")) is complex


def test_expression_imports_follow_direct_item_updates():
    import json

    from sparkwheel import Expression

    expression = Expression("$import math")
    assert expression.evaluate() is math
    expression.update_config("$import json")
    assert expression.evaluate() is json


def test_whitespace_after_expression_prefix_is_accepted():
    assert Config(data={"value": "$  @n + 1", "n": 2}).resolve("value") == 3


@pytest.mark.parametrize("expression", ["$import math\n@x + 1", "$import math #comment\n@x + 1"])
def test_reference_at_new_statement_is_not_matrix_multiplication(expression):
    config = Config(data={"x": 2, "value": expression})
    assert config.resolve("value") == 3
    assert config.retain().scope().resolve("value") == 3


def test_reference_after_yield_from_and_adjacent_python_keyword():
    config = Config(data={"xs": [1, 2], "flag": False, "value": "$(lambda: (yield from @xs))()", "negated": "$not@flag"})
    assert list(config.resolve("value")) == [1, 2]
    assert config.resolve("negated") is True
    scope = config.retain().scope()
    assert list(scope.resolve("value")) == [1, 2]
    assert scope.resolve("negated") is True


def test_unevaluated_import_expression_wrapper_does_not_depend_on_prior_resolution_order():
    source = {"a": "$1", "b": "$import math; math.sqrt(@x)", "x": 4}
    first = Config(data=source)
    first.resolve("a", eval_expr=False)
    after_other = first.resolve("b", eval_expr=False)
    direct = Config(data=source).resolve("b", eval_expr=False)
    assert after_other.get_config() == direct.get_config() == "$import math; math.sqrt(__local_refs['x'])"
    assert first.resolve("b", eval_expr=False) is after_other
    assert first.resolve("b") == 2.0
