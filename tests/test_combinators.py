"""Tests for the parser combinators."""

from typing import assert_type

import pytest

from infinity_parse import (
    ConvertError,
    MatchError,
    Parser,
    alt,
    first_field,
    recursive,
    scan,
    sep_by,
    split_top,
)


def test_alt_picks_the_first_parser_that_matches() -> None:
    value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
    assert value('"hi"') == "hi"
    assert value("hi") == "hi"


def test_alt_raises_when_every_parser_fails() -> None:
    value = alt(scan[int]("x={}"), scan[int]("y={}"))
    with pytest.raises(MatchError, match="no alternative matched"):
        value("z=1")


def test_alt_does_not_swallow_convert_errors() -> None:
    value = alt(scan[int]("{}"), scan[str]("{}"))
    with pytest.raises(ConvertError):
        value("abc")


def test_recursive_supports_nested_input() -> None:
    def wrapped(thunk: Parser[str]) -> Parser[str]:
        def group(text: str) -> str:
            if not (text.startswith("(") and text.endswith(")")):
                raise MatchError(f"not wrapped: {text!r}")
            return thunk(text[1:-1])

        return alt(group, first_field(scan[str]("{}")))

    parse = recursive(wrapped)
    assert parse("(((x)))") == "x"
    assert parse("x") == "x"


def test_sep_by_parses_separated_members() -> None:
    numbers = sep_by(first_field(scan[int]("{}")))
    assert numbers("1, 2, 3") == [1, 2, 3]


def test_sep_by_uses_a_custom_separator() -> None:
    words = sep_by(first_field(scan[str]("{}")), separator=";")
    assert words("a; b") == ["a", "b"]


def test_split_top_protects_bracketed_separators() -> None:
    assert split_top("a,b[c,d],e", ",") == ["a", "b[c,d]", "e"]
    assert split_top("{a,b},c", ",") == ["{a,b}", "c"]
    assert split_top("solo", ",") == ["solo"]


def test_first_field_unwraps_a_single_field_scanner() -> None:
    number = first_field(scan[int]("{}"))
    assert number("42") == 42
    assert_type(number, Parser[int])


def test_first_field_unwraps_the_first_of_several_fields() -> None:
    pair = scan[int, str]("{} {}")
    assert first_field(pair)("1 hello") == 1
