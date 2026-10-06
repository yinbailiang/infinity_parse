"""Runtime engine for :mod:`infinity_parse`: resolve field metas, then scan input.

Two responsibilities, with no type-level semantics:

* :func:`resolve_field` -- turn one field's meta (a bare declared converter
  plus an optional :class:`Converter` spec) into a concrete converter configuration
  (:class:`Field`);
* :class:`Template` -- validate a configuration, compile the template regex
  and ``scan`` input strings into tuples.
"""

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, get_origin

# The default field pattern: non-empty, single-line (no DOTALL) and lazy.
DEFAULT_PATTERN = r".+?"
_PLACEHOLDER = "{}"
_WHITESPACE = re.compile(r"\s+")


class ScanError(ValueError):
    """Base failure while scanning: a ``MatchError`` or a ``ConvertError``."""


class MatchError(ScanError):
    """Input did not match the template (a soft failure).

    Ordered-choice combinators fall through to the next alternative on this
    one. A branch that matched but failed to convert raises ``ConvertError``
    instead, which aborts the choice so its diagnostics are never swallowed.
    """


class ConvertError(ScanError):
    """A field matched but its converter failed (a hard failure).

    The message carries the field number, the text and its offset; the
    underlying error is chained through ``__cause__``.
    """


@dataclass(frozen=True)
class Converter[T]:
    """Per-field converter spec, passed as ``Annotated[T, Converter(...)]`` metadata.

    ``fn`` converts the matched text; ``pattern`` is the regex used to capture
    this field (inserted into the template regex as-is); ``strip`` strips the
    matched text before conversion; ``name`` labels the field in error messages
    (defaults to the callable's name); ``flags`` are ``re`` flags applied to
    ``pattern``. Several specs on one field compete in declaration order: the
    first branch whose pattern matches wins, and if its ``fn`` then raises, the
    scan fails as a whole (no fallback to the remaining branches).
    """

    fn: Callable[[str], T]
    pattern: str = DEFAULT_PATTERN
    strip: bool = True
    name: str | None = None
    flags: int = 0


@dataclass(frozen=True)
class Field:
    """One placeholder: converter branches competing in declaration order."""

    converters: tuple[Converter[Any], ...]


def _converter_name(converter: object) -> str | None:
    """Return the display name of ``converter`` (used to label fields)."""
    name = getattr(converter, "__name__", None)
    if isinstance(name, str):
        return name
    origin = get_origin(converter)
    if origin is not None:
        name = getattr(origin, "__name__", None)
        if isinstance(name, str):
            return name
    return None


def _label(converter: Converter[Any]) -> str:
    """Display name of one converter branch in error messages."""
    return converter.name or _converter_name(converter.fn) or repr(converter.fn)


def _literal_converter(origin: type[Any]) -> Callable[[str], Any]:
    return lambda text: origin(ast.literal_eval(text))


_BOOL_VALUES = {"true": True, "false": False, "1": True, "0": False}


def _bool_converter(text: str) -> bool:
    value = _BOOL_VALUES.get(text.casefold())
    if value is None:
        raise ValueError(f"cannot parse {text!r} as bool")
    return value


# Keyed by the origin *object* (not by name), so user classes that happen to be
# named ``dict``, ``list``, ``bool``, ... never pick up a built-in default.
_BUILTIN_CONVERTERS: dict[object, Callable[[str], Any]] = {
    bool: _bool_converter,
    dict: _literal_converter(dict),
    frozenset: _literal_converter(frozenset),
    list: _literal_converter(list),
    set: _literal_converter(set),
    tuple: _literal_converter(tuple),
}


def _default_converter(converter: object) -> Callable[[str], Any] | None:
    """Return the built-in default converter for supported built-in types."""
    origin = get_origin(converter)
    return _BUILTIN_CONVERTERS.get(origin if origin is not None else converter)


def resolve_field(declared: Any, convs: list[Converter[Any]]) -> Field:
    """Resolve one field's meta into its converter branches (meta -> converters).

    User-provided ``Converter`` specs become the branches, in order. Without
    any, one branch is synthesized from the declared type: the built-in default
    for supported containers, otherwise the declared type used as a callable.
    """
    if convs:
        return Field(converters=tuple(convs))
    branch: Converter[Any] = Converter(
        fn=_default_converter(declared) or declared,
        name=_converter_name(declared),
    )
    return Field(converters=(branch,))


def _literal_to_pattern(text: str) -> str:
    """Escape literal template text; whitespace runs become ``\\s+``."""
    pieces: list[str] = []
    position = 0
    for match in _WHITESPACE.finditer(text):
        pieces.append(re.escape(text[position : match.start()]))
        pieces.append(r"\s+")
        position = match.end()
    pieces.append(re.escape(text[position:]))
    return "".join(pieces)


_INLINE_FLAGS: tuple[tuple[int, str], ...] = (
    (re.IGNORECASE, "i"),
    (re.MULTILINE, "m"),
    (re.DOTALL, "s"),
    (re.VERBOSE, "x"),
    (re.ASCII, "a"),
)
_INLINE_FLAG_MASK = re.IGNORECASE | re.MULTILINE | re.DOTALL | re.VERBOSE | re.ASCII


def _scoped(pattern: str, flags: int) -> str:
    """Wrap ``pattern`` in scoped inline flags (e.g. ``(?i:...)``)."""
    if not flags:
        return pattern
    if flags & ~_INLINE_FLAG_MASK:
        raise ValueError(f"unsupported re flags for a field pattern: {flags:#x}")
    letters = "".join(letter for bit, letter in _INLINE_FLAGS if flags & bit)
    return f"(?{letters}:{pattern})"


@lru_cache(maxsize=1024)
def _segments(template: str) -> tuple[str | None, ...]:
    """Split ``template`` into literal segments and ``None`` placeholders.

    ``{{`` and ``}}`` escape literal braces; a single brace is an error.
    """
    segments: list[str | None] = []
    literal: list[str] = []
    text = template.strip()
    position = 0
    while position < len(text):
        character = text[position]
        if character == "{":
            if text.startswith("{{", position):
                literal.append("{")
                position += 2
            elif text.startswith(_PLACEHOLDER, position):
                segments.append("".join(literal))
                literal.clear()
                segments.append(None)
                position += 2
            else:
                raise ValueError(
                    f"single '{{' in template {template!r}; escape literal "
                    "braces as '{{' and '}}'"
                )
        elif character == "}":
            if text.startswith("}}", position):
                literal.append("}")
                position += 2
            else:
                raise ValueError(
                    f"single '}}' in template {template!r}; escape literal "
                    "braces as '{{' and '}}'"
                )
        else:
            literal.append(character)
            position += 1
    segments.append("".join(literal))
    return tuple(segments)


def _branch_group(index: int, branch: int) -> str:
    """Regex group name capturing one branch's own match for a field."""
    return f"s{index}b{branch}"


def _field_chunk(index: int, field: Field) -> str:
    """One field's regex: its converter branches as an ordered alternation."""
    converters = field.converters
    if len(converters) == 1:
        single = converters[0]
        return f"(?P<s{index}>{_scoped(single.pattern, single.flags)})"
    branches = "|".join(
        f"(?P<{_branch_group(index, branch)}>{_scoped(conv.pattern, conv.flags)})"
        for branch, conv in enumerate(converters)
    )
    return f"(?P<s{index}>{branches})"


@lru_cache(maxsize=1024)
def _compile(template: str, fields: tuple[Field, ...]) -> re.Pattern[str]:
    """Compile ``template`` into a regex with one named group per placeholder."""
    chunks: list[str] = []
    placeholder = 0
    for segment in _segments(template):
        if segment is None:
            chunks.append(_field_chunk(placeholder, fields[placeholder]))
            placeholder += 1
        else:
            chunks.append(_literal_to_pattern(segment))
    return re.compile("".join(chunks))


def _winner(match: re.Match[str], index: int, field: Field) -> int:
    """Index of the branch whose pattern produced the field's match."""
    if len(field.converters) == 1:
        return 0
    for branch, _ in enumerate(field.converters):
        if match.group(_branch_group(index, branch)) is not None:
            return branch
    raise AssertionError(f"no converter branch matched field {index}")


class Template:
    """A validated, compiled template, ready to scan input."""

    def __init__(self, template: str, fields: tuple[Field, ...]) -> None:
        # Fail fast on converters that cannot go into the compile cache.
        hash(fields)
        for field in fields:
            if not field.converters:
                raise ValueError("each field requires at least one converter")
            for converter in field.converters:
                if not callable(converter.fn):
                    raise TypeError(
                        f"converters must be callable, got {converter.fn!r}"
                    )
        placeholders = sum(segment is None for segment in _segments(template))
        if placeholders != len(fields):
            raise ValueError(
                f"template {template!r} has {placeholders} placeholder(s) "
                f"but {len(fields)} converter type(s) were given"
            )
        self.template = template
        self.fields = fields
        self._pattern = _compile(template, fields)

    def scan(self, input_value: str) -> tuple[Any, ...]:
        """Scan ``input_value``: match the template and convert each field."""
        match = self._pattern.fullmatch(input_value.strip())
        if match is None:
            raise MatchError(
                f"input {input_value!r} does not match template {self.template!r}"
            )
        values: list[Any] = []
        for index, field in enumerate(self.fields):
            converter = field.converters[_winner(match, index, field)]
            raw = match.group(f"s{index}")
            text = raw.strip() if converter.strip else raw
            try:
                values.append(converter.fn(text))
            except Exception as error:
                # Report the offset within the original input, not the stripped one.
                shift = len(input_value) - len(input_value.lstrip())
                offset = shift + match.start(f"s{index}")
                raise ConvertError(
                    f"cannot convert field {index + 1} ({text!r}) at offset "
                    f"{offset} using {_label(converter)}"
                ) from error
        return tuple(values)
