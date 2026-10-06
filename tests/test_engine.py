"""Tests for the backend engine: resolve metas, then scan."""

import json
import re
from typing import Any

import pytest

from infinity_parse.engine import (
    Converter,
    ConvertError,
    Field,
    MatchError,
    ScanError,
    Template,
    resolve_field,
)


def _field(fn: Any, pattern: str = r".+?", name: str | None = None) -> Field:
    """Shorthand for a single-branch, zero-flags, stripping field."""
    converter: Converter[Any] = Converter(fn=fn, pattern=pattern, name=name)
    return Field(converters=(converter,))


def test_engine_parses_explicit_configuration() -> None:
    template = Template("x={}", (_field(int, pattern=r"\d+", name="x"),))
    assert template.fullmatch("x=42") == (42,)


def test_engine_reports_mismatch_and_conversion_failure() -> None:
    strict = Template("{}", (_field(int, pattern=r"\d+", name="int"),))
    with pytest.raises(ScanError, match="does not match"):
        strict.fullmatch("abc")
    loose = Template("{}", (_field(int, name="int"),))
    with pytest.raises(ScanError, match="using int"):
        loose.fullmatch("abc")


def test_engine_validates_configuration() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        Template("{} {}", (_field(int, name="int"),))
    with pytest.raises(TypeError, match="callable"):
        Template("{}", (_field(42),))
    with pytest.raises(ValueError, match="at least one converter"):
        Template("{}", (Field(converters=()),))


def test_engine_resolves_field_meta_to_converter() -> None:
    custom = resolve_field(dict, [Converter(json.loads, name="dict")])
    assert custom.converters[0].fn is json.loads
    assert custom.converters[0].name == "dict"
    assert resolve_field(int, []).converters[0].fn is int
    default = resolve_field(dict, [])
    assert default.converters[0].fn("{}") == {}


def test_engine_escapes_literal_braces() -> None:
    template = Template("{{}}", ())
    assert template.fullmatch("{}") == ()
    with pytest.raises(ValueError, match="single"):
        Template("}", ())


def test_engine_rejects_unhashable_converters() -> None:
    class Unhashable:
        def __eq__(self, other: object) -> bool:
            return self is other

        def __call__(self, raw: str) -> str:
            return raw

    converter: Converter[str] = Converter(fn=Unhashable())
    fields = (Field(converters=(converter,)),)
    with pytest.raises(TypeError, match="unhashable"):
        Template("{}", fields)


def test_engine_distinguishes_match_and_convert_failures() -> None:
    with pytest.raises(MatchError):
        Template("x", ()).fullmatch("y")
    loose = Template("{}", (_field(int, name="int"),))
    with pytest.raises(ConvertError) as exc_info:
        loose.fullmatch("abc")
    assert isinstance(exc_info.value, ScanError)
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_engine_branches_compete_in_declaration_order() -> None:
    field = Field(
        converters=(
            Converter(fn=lambda raw: f"number:{raw}", pattern=r"\d+"),
            Converter(fn=lambda raw: f"word:{raw}", pattern=r"[a-z]+"),
        )
    )
    template = Template("{}", (field,))
    assert template.fullmatch("42") == ("number:42",)
    assert template.fullmatch("abc") == ("word:abc",)
    with pytest.raises(MatchError):
        template.fullmatch("!!")


def test_engine_first_matching_branch_wins() -> None:
    field = Field(
        converters=(
            Converter(fn=lambda raw: "first", pattern=r"\w+"),
            Converter(fn=lambda raw: "second", pattern=r".+"),
        )
    )
    template = Template("{}", (field,))
    assert template.fullmatch("abc") == ("first",)  # both branches could match
    assert template.fullmatch("a b") == ("second",)  # only the fallback matches


def test_engine_converter_failure_does_not_fall_through() -> None:
    field = Field(
        converters=(
            Converter(fn=int, pattern=r"\w+", name="int"),
            Converter(fn=str, pattern=r".+?", name="str"),
        )
    )
    with pytest.raises(ConvertError, match="using int") as exc_info:
        Template("{}", (field,)).fullmatch("abc")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_engine_branch_flags_apply_per_branch() -> None:
    field = Field(
        converters=(
            Converter(fn=str, pattern=r"\d+", name="digits"),
            Converter(fn=str, pattern=r"[a-z]+", flags=re.IGNORECASE, name="letters"),
        )
    )
    template = Template("{}", (field,))
    assert template.fullmatch("42") == ("42",)
    assert template.fullmatch("HeLLo") == ("HeLLo",)


def test_engine_branch_selection_is_per_field() -> None:
    number_or_word = Field(
        converters=(
            Converter(fn=int, pattern=r"\d+", name="number"),
            Converter(fn=str, pattern=r"[a-z]+", name="word"),
        )
    )
    template = Template("{} {}", (number_or_word, number_or_word))
    assert template.fullmatch("42 abc") == (42, "abc")
    assert template.fullmatch("abc 42") == ("abc", 42)


def test_engine_search_finds_first_match_anywhere() -> None:
    template = Template("x={}", (_field(int, pattern=r"\d+", name="x"),))
    assert template.search("prefix x=42 suffix") == (42,)
    assert template.search("no dice") is None


def test_engine_search_reports_offset_in_original_input() -> None:
    template = Template("age={}", (_field(int, pattern=r"[a-z]+", name="age"),))
    with pytest.raises(ConvertError, match="at offset 8") as exc_info:
        template.search("abc age=oops")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_engine_findall_returns_every_match() -> None:
    template = Template("x={}", (_field(int, pattern=r"\d+", name="x"),))
    assert template.findall("x=1, x=2, x=30") == [(1,), (2,), (30,)]
    assert template.findall("nothing to see") == []


def test_engine_findall_selects_a_branch_per_match() -> None:
    field = Field(
        converters=(
            Converter(fn=lambda raw: f"number:{raw}", pattern=r"\d+"),
            Converter(fn=lambda raw: f"word:{raw}", pattern=r"[a-z]+"),
        )
    )
    template = Template("{}", (field,))
    assert template.findall("42 abc 7") == [
        ("number:42",),
        ("word:abc",),
        ("number:7",),
    ]


def test_engine_findall_multi_field_matches() -> None:
    pair = Field(
        converters=(
            Converter(fn=int, pattern=r"\d+", name="number"),
            Converter(fn=str, pattern=r"[a-z]+", name="word"),
        )
    )
    template = Template("{} {}", (pair, pair))
    assert template.findall("1 a, 2 b") == [(1, "a"), (2, "b")]


def test_engine_findall_fails_hard_on_conversion_error() -> None:
    template = Template("{}", (_field(int, pattern=r"\w+", name="int"),))
    with pytest.raises(ConvertError, match="at offset 2"):
        template.findall("1 x 2")
