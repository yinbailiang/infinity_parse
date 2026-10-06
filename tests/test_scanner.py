"""Tests for the scan front-end."""

import json
import re
import types
import warnings
from typing import Annotated, Any, assert_type, cast, get_args, get_origin

import pytest

from infinity_parse import (
    Converter,
    ConvertError,
    MatchError,
    ScanError,
    scan,
    scanall,
    search,
)

# PEP 695 aliases must be at module scope (pyright rule).
type Digits = Annotated[int, Converter(int, pattern=r"\d+", name="digits")]
type Again = Digits
type Key = Annotated[
    str,
    Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="escaped"),
    Converter(str, pattern=r"[^=\s]+", name="bare"),
]
type Value = Annotated[
    str,
    Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="escaped"),
    Converter(str, pattern=r".*", name="bare"),
]


class Hex:
    """Example custom converter that parses hexadecimal integers."""

    def __init__(self, raw: str) -> None:
        self.value = int(raw, 16)


def test_canonical_example() -> None:
    a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
    assert (a, b, c) == (1, 2.5, "hello")


def test_inferred_result_types() -> None:
    a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
    assert_type(a, int)
    assert_type(b, float)
    assert_type(c, str)
    assert_type(scan[int, int]("{} {}")("7 8"), tuple[int, int])
    assert_type(scan[str]("{}")("x"), tuple[str])
    assert_type(
        scan[Annotated[dict[str, str], Converter(json.loads)]]("{}")(
            '{"key": "value"}'
        ),
        tuple[dict[str, str]],
    )


def test_parser_is_reusable() -> None:
    parse_pair = scan[int, int]("{} {}")
    assert parse_pair("7 8") == (7, 8)
    assert parse_pair("9 10") == (9, 10)


def test_search_front_end_returns_first_match() -> None:
    parse = search[Digits]("{}")
    assert parse("x 42 y") == (42,)
    assert parse("nothing") is None


def test_scanall_front_end_returns_all_matches() -> None:
    assert scanall[Digits]("x {}")("x 1, x 2") == [(1,), (2,)]


def test_literal_text_in_template() -> None:
    x, y = scan[int, int]("x={}, y={}")("x= 1,   y=2")
    assert (x, y) == (1, 2)


def test_log_line() -> None:
    program, errors, warnings = scan[str, int, int]("{} - {} errors, {} warnings")(
        "/usr/sbin/sendmail - 0 errors, 4 warnings"
    )
    assert (program, errors, warnings) == ("/usr/sbin/sendmail", 0, 4)


def test_whitespace_is_collapsed_and_trimmed() -> None:
    first, second = scan[str, str]("{} {}")("  hello   world  ")
    assert (first, second) == ("hello", "world")


def test_newlines_count_as_whitespace() -> None:
    number, word = scan[int, str]("{} {}")("1\nhello")
    assert (number, word) == (1, "hello")


def test_custom_converter() -> None:
    (parsed,) = scan[Hex]("{}")("ff")
    assert parsed.value == 255


def test_more_than_ten_fields() -> None:
    result = scan[int, int, int, int, int, int, int, int, int, int, int, int](
        "{} {} {} {} {} {} {} {} {} {} {} {}"
    )("1 2 3 4 5 6 7 8 9 10 11 12")
    assert result == tuple(range(1, 13))
    assert_type(result[0], int)


def test_scan_error_is_a_value_error() -> None:
    assert issubclass(ScanError, ValueError)


def test_no_match_raises_scan_error() -> None:
    with pytest.raises(ScanError, match="does not match"):
        scan[int, int]("{} {}")("only-one")


def test_exact_match_required() -> None:
    with pytest.raises(ScanError, match="does not match"):
        scan[str]("{}?")("ok!")


def test_conversion_failure_raises_scan_error() -> None:
    with pytest.raises(ScanError, match="cannot convert field 2") as exc_info:
        scan[int, int]("{} {}")("1 zz")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_converter_count_must_match_placeholders() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        scan[int]("{} {}")


def test_template_without_placeholders_is_rejected() -> None:
    with pytest.raises(ValueError):
        scan[int]("hello")


def test_call_without_converter_types_is_rejected() -> None:
    # Calling without converter types is rejected.
    with pytest.raises(TypeError, match="at least one converter"):
        cast(Any, scan)("{}")


def test_non_callable_converter_is_rejected() -> None:
    with pytest.raises(TypeError, match="callable"):
        cast(Any, scan)[42]("{}")


def test_converter_custom_callable() -> None:
    parse = scan[Annotated[dict[str, str], Converter(json.loads, name="dict")]]("{}")
    assert parse('{"key": "value"}') == ({"key": "value"},)


def test_builtin_container_type_defaults() -> None:
    (mapping,) = scan[dict[str, str]]("{}")('{"key": "value"}')
    assert mapping == {"key": "value"}
    (items,) = scan[list[int]]("{}")("[1, 2, 3]")
    assert items == [1, 2, 3]
    (pair,) = scan[tuple[int, str]]("{}")("(1, 'a')")
    assert pair == (1, "a")
    (members,) = scan[set[int]]("{}")("{1, 2}")
    assert members == {1, 2}
    (frozen,) = scan[frozenset[int]]("{}")("(1, 2)")
    assert frozen == frozenset({1, 2})


def test_bare_container_gets_default() -> None:
    # Bare ``dict`` also gets the literal default; the cast silences pyright.
    untyped = cast(Any, scan)[dict]("{}")
    assert untyped('{"key": "value"}') == ({"key": "value"},)


def test_python_literal_syntax_is_used() -> None:
    (mapping,) = scan[dict[str, int]]("{}")("{'a': 0x10}")
    assert mapping == {"a": 16}


def test_converter_replaces_builtin_default() -> None:
    parse = scan[
        Annotated[list[str], Converter(lambda raw: raw.split(","), name="items")]
    ]("{}")
    assert parse("a,b,c") == (["a", "b", "c"],)


def test_builtin_default_failure_is_scan_error() -> None:
    with pytest.raises(ScanError, match="using list") as exc_info:
        scan[list[int]]("{}")("[1, 2")
    assert isinstance(exc_info.value.__cause__, SyntaxError)


def test_annotated_metadata_is_stripped() -> None:
    parsed = scan[Annotated[dict[str, str], "json"]]("{}")('{"key": "value"}')
    assert parsed == ({"key": "value"},)
    assert_type(parsed, tuple[dict[str, str]])


def test_converter_patterns_and_names() -> None:
    parse = scan[
        Annotated[int, Converter(int, pattern=r"\d+", name="age")],
        Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
    ]("age={} name={}")
    age, name = parse('age=42 name="kim"')
    assert (age, name) == (42, '"kim"')
    assert_type(age, int)
    assert_type(name, str)


def test_escaped_string_pattern_decodes_escapes() -> None:
    parse = scan[
        Annotated[
            str,
            Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="name"),
        ]
    ]("{}")
    assert parse(r'"kim"') == ("kim",)
    assert parse(r'"kim \"the fox\""') == ('kim "the fox"',)
    assert parse(r'"C:\\path\\to\\file"') == ("C:\\path\\to\\file",)
    assert parse(r'"line1\nline2"') == ("line1\nline2",)
    with pytest.raises(ConvertError, match="using name") as exc_info:
        parse(r'"a\x"')
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_converter_pattern_is_enforced() -> None:
    parse = scan[Annotated[int, Converter(int, pattern=r"\d+")]]("{}")
    assert parse("42") == (42,)
    with pytest.raises(ScanError, match="does not match"):
        parse("abc")


def test_converter_name_labels_errors() -> None:
    parse = scan[Annotated[int, Converter(int, pattern=r"[a-z]+", name="age")]](
        "age={}"
    )
    with pytest.raises(ScanError, match="using age"):
        parse("age=abc")


def test_converter_strip_flag() -> None:
    trimmed = scan[Annotated[str, Converter(str)]]("{}!")
    assert trimmed("hi !") == ("hi",)
    kept = scan[Annotated[str, Converter(str, strip=False)]]("{}!")
    assert kept("hi !") == ("hi ",)


def test_converter_flags() -> None:
    parse = scan[
        Annotated[str, Converter(str, pattern=r"[a-z]+", flags=re.IGNORECASE)]
    ]("{}")
    assert parse("HeLLo") == ("HeLLo",)


def test_converter_found_among_other_metadata() -> None:
    parse = scan[Annotated[int, "doc", Converter(int, pattern=r"\d+")]]("{}")
    assert parse("7") == (7,)


def test_converter_bad_pattern_raises_at_construction() -> None:
    with pytest.raises(re.error):
        scan[Annotated[int, Converter(int, pattern="[")]]("{}")


def test_multiple_converter_specs_compete_in_declaration_order() -> None:
    parse = scan[
        Annotated[
            str,
            Converter(lambda raw: "first", pattern=r"\d+"),
            Converter(lambda raw: "second", pattern=r"[a-z]+"),
        ]
    ]("{}")
    # First matching branch wins.
    assert parse("42") == ("first",)
    assert parse("abc") == ("second",)
    with pytest.raises(MatchError):
        parse("!!")


def test_multiple_converter_specs_do_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        parse = scan[
            Annotated[
                str,
                Converter(str, pattern=r"\d+"),
                Converter(str, pattern=r"[a-z]+"),
            ]
        ]("{}")
    assert parse("42") == ("42",)


def test_first_matching_branch_wins() -> None:
    parse = scan[
        Annotated[
            str,
            Converter(lambda raw: "first", pattern=r"\w+"),
            Converter(lambda raw: "second", pattern=r".+"),
        ]
    ]("{}")
    assert parse("abc") == ("first",)  # both could match
    assert parse("a b") == ("second",)  # only the fallback matches


def test_failing_converter_aborts_instead_of_falling_through() -> None:
    parse = scan[
        Annotated[
            int,
            Converter(int, pattern=r"\w+"),
            Converter(str, pattern=r".+?"),  # would match, but must not be tried
        ]
    ]("{}")
    assert parse("42") == (42,)
    with pytest.raises(ConvertError, match="using int"):
        parse("abc")


def test_nested_converter_layers_compete_innermost_first() -> None:
    parse = scan[
        Annotated[
            Annotated[str, Converter(lambda raw: "inner")],
            Converter(lambda raw: "outer"),
        ]
    ]("{}")
    # Nested Annotated: inner branch competes first.
    assert parse("x") == ("inner",)


def test_pep695_alias_meta_expands_like_inline() -> None:
    # Runtime unwraps aliases like pyright expands them.
    parse = scan[Digits]("{}")
    assert parse("42") == (42,)
    assert_type(parse("42"), tuple[int])
    with pytest.raises(MatchError):
        parse("abc")


def test_pep695_alias_chain_unwraps_recursively() -> None:
    assert scan[Again]("{}")("7") == (7,)


def test_pep695_aliases_compete_per_field() -> None:
    line = scan[Key, Value]("{}={}")
    assert line("k=v") == ("k", "v")
    assert line('k="v v"') == ("k", "v v")
    assert_type(line("k=v"), tuple[str, str])


def test_nested_annotated_layers_are_flattened() -> None:
    parse = scan[
        Annotated[Annotated[int, Converter(int, pattern=r"\d+", name="age")], "doc"]
    ]("age={}")
    assert parse("age=42") == (42,)


def test_specialization_is_a_real_generic_alias() -> None:
    alias = scan[int, str]
    assert get_origin(alias) is scan
    assert get_args(alias) == (int, str)
    assert isinstance(alias, types.GenericAlias)
    parser = alias("{} {}")
    assert getattr(parser, "__orig_class__", None) == alias


def test_subscribed_aliases_are_independent() -> None:
    # Subscriptions keep separate state.
    binder = scan[int]
    other = scan[str]
    parse_int = binder("{}")
    parse_str = other("{}")
    assert parse_int("42") == (42,)
    assert parse_str("hi") == ("hi",)
    assert parse_int("7") == (7,)


def test_escaped_braces_are_literal() -> None:
    parse = scan[int]("{{}}={}")
    assert parse("{}= 42") == (42,)


def test_literal_braces_around_placeholder() -> None:
    parse = scan[int]("{{{}}}")
    assert parse("{42}") == (42,)


def test_single_braces_are_rejected() -> None:
    with pytest.raises(ValueError, match="single"):
        scan[int]("{ x }")
    with pytest.raises(ValueError, match="single"):
        scan[int]("just }")


def test_bool_converter_accepts_common_literals() -> None:
    parse_bool = scan[bool]("{}")
    assert parse_bool("true") == (True,)
    assert parse_bool("False") == (False,)
    assert parse_bool("1") == (True,)
    assert parse_bool("0") == (False,)
    assert_type(parse_bool("true"), tuple[bool])


def test_bool_converter_rejects_unknown_text() -> None:
    with pytest.raises(ScanError, match="using bool") as exc_info:
        scan[bool]("{}")("yes")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_conversion_error_includes_offset() -> None:
    with pytest.raises(ScanError, match="at offset 2"):
        scan[int, int]("{} {}")("1 zz")
    with pytest.raises(ScanError, match="at offset 4") as exc_info:
        scan[int, int]("{} {}")("  1 zz")
    assert "cannot convert field 2" in str(exc_info.value)


def test_converter_can_nest_another_scanner() -> None:
    point = scan[int, int]("{} {}")
    parse = scan[
        Annotated[
            tuple[int, int],
            Converter(point, pattern=r"(?<=\[).+?(?=\])", name="point"),
        ]
    ]("point=[{}]")
    assert_type(parse("point=[1 2]"), tuple[tuple[int, int]])
    assert parse("point=[1 2]") == ((1, 2),)


def test_nested_scanner_failure_chains_causes() -> None:
    point = scan[int, int]("{} {}")
    parse = scan[
        Annotated[
            tuple[int, int],
            Converter(point, pattern=r"(?<=\[).+?(?=\])", name="point"),
        ]
    ]("point=[{}]")
    with pytest.raises(ScanError, match="using point") as exc_info:
        parse("point=[oops]")
    assert isinstance(exc_info.value.__cause__, ScanError)


def test_match_and_convert_errors_are_distinct() -> None:
    with pytest.raises(MatchError):
        scan[int]("x={}")("y")
    with pytest.raises(ConvertError) as exc_info:
        scan[int]("{}")("abc")
    assert isinstance(exc_info.value, ScanError)
