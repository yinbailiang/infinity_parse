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
    assert template.scan("x=42") == (42,)


def test_engine_reports_mismatch_and_conversion_failure() -> None:
    strict = Template("{}", (_field(int, pattern=r"\d+", name="int"),))
    with pytest.raises(ScanError, match="does not match"):
        strict.scan("abc")
    loose = Template("{}", (_field(int, name="int"),))
    with pytest.raises(ScanError, match="using int"):
        loose.scan("abc")


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
    assert template.scan("{}") == ()
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
        Template("x", ()).scan("y")
    loose = Template("{}", (_field(int, name="int"),))
    with pytest.raises(ConvertError) as exc_info:
        loose.scan("abc")
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
    assert template.scan("42") == ("number:42",)
    assert template.scan("abc") == ("word:abc",)
    with pytest.raises(MatchError):
        template.scan("!!")


def test_engine_first_matching_branch_wins() -> None:
    field = Field(
        converters=(
            Converter(fn=lambda raw: "first", pattern=r"\w+"),
            Converter(fn=lambda raw: "second", pattern=r".+"),
        )
    )
    template = Template("{}", (field,))
    assert template.scan("abc") == ("first",)  # both branches could match
    assert template.scan("a b") == ("second",)  # only the fallback matches


def test_engine_converter_failure_does_not_fall_through() -> None:
    field = Field(
        converters=(
            Converter(fn=int, pattern=r"\w+", name="int"),
            Converter(fn=str, pattern=r".+?", name="str"),
        )
    )
    with pytest.raises(ConvertError, match="using int") as exc_info:
        Template("{}", (field,)).scan("abc")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_engine_branch_flags_apply_per_branch() -> None:
    field = Field(
        converters=(
            Converter(fn=str, pattern=r"\d+", name="digits"),
            Converter(fn=str, pattern=r"[a-z]+", flags=re.IGNORECASE, name="letters"),
        )
    )
    template = Template("{}", (field,))
    assert template.scan("42") == ("42",)
    assert template.scan("HeLLo") == ("HeLLo",)


def test_engine_branch_selection_is_per_field() -> None:
    number_or_word = Field(
        converters=(
            Converter(fn=int, pattern=r"\d+", name="number"),
            Converter(fn=str, pattern=r"[a-z]+", name="word"),
        )
    )
    template = Template("{} {}", (number_or_word, number_or_word))
    assert template.scan("42 abc") == (42, "abc")
    assert template.scan("abc 42") == ("abc", 42)
