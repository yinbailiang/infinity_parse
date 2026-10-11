"""Runtime engine for :mod:`infinity_parse`: compile templates, then scan input."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

# Default capture pattern for "{}" fields.
RE = re
DEFAULT_PATTERN = r".+?"
PLACEHOLDER = "{}"
WHITESPACE: RE.Pattern[str] = RE.compile(r"\s+")


class ScanError(ValueError):
    """Base class for scan failures.

    ``MatchError`` and ``ConvertError`` add machine-readable attributes for
    the failed match or conversion (see their docstrings).
    """


class MatchError(ScanError):
    """The input did not match the template (soft failure).

    ``input_value`` and ``template`` carry the scanned input and the template
    text when available, and ``None`` otherwise.
    """

    def __init__(
        self,
        message: str,
        /,
        *,
        input_value: str | None = None,
        template: str | None = None,
    ) -> None:
        super().__init__(message)
        self.input_value = input_value
        self.template = template


class ConvertError(ScanError):
    """A field matched but its converter failed (hard failure).

    Structured details mirror the message: ``field`` (1-based field number),
    ``offset`` (start of the captured text in the original input), ``text``
    (the text given to the converter) and ``converter`` (display label), plus
    ``input_value`` and ``template`` when available.
    """

    def __init__(
        self,
        message: str,
        /,
        *,
        field: int | None = None,
        offset: int | None = None,
        text: str | None = None,
        converter: str | None = None,
        input_value: str | None = None,
        template: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.offset = offset
        self.text = text
        self.converter = converter
        self.input_value = input_value
        self.template = template


@dataclass(frozen=True)
class Converter[T]:
    """Per-field config for ``Annotated[T, Converter(...)]``.

    ``fn`` converts the captured text; ``pattern`` captures the field;
    ``strip`` trims it first; ``name`` labels errors; ``flags`` are ``re``
    flags applied to the pattern.
    """

    fn: Callable[[str], T]
    pattern: str = DEFAULT_PATTERN
    strip: bool = True
    name: str | None = None
    flags: int = 0


@dataclass(frozen=True)
class Field:
    """One ``{}`` placeholder: converter branches competing in order."""

    converters: tuple[Converter[Any], ...]


def _label(converter: Converter[Any]) -> str:
    """Display name of one converter branch in error messages."""
    name = getattr(converter.fn, "__name__", None)
    if not isinstance(name, str):
        name = repr(converter.fn)
    return converter.name or name


def _literal_to_pattern(text: str) -> str:
    """Escape literal template text; whitespace runs become ``\\s+``."""
    pieces: list[str] = []
    position = 0
    for match in WHITESPACE.finditer(text):
        pieces.append(RE.escape(text[position : match.start()]))
        pieces.append(r"\s+")
        position = match.end()
    pieces.append(RE.escape(text[position:]))
    return "".join(pieces)


_INLINE_FLAGS: tuple[tuple[int, str], ...] = (
    (RE.IGNORECASE, "i"),
    (RE.MULTILINE, "m"),
    (RE.DOTALL, "s"),
    (RE.VERBOSE, "x"),
    (RE.ASCII, "a"),
)
_INLINE_FLAG_MASK = RE.IGNORECASE | RE.MULTILINE | RE.DOTALL | RE.VERBOSE | RE.ASCII


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
            elif text.startswith(PLACEHOLDER, position):
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
def _compile(template: str, fields: tuple[Field, ...]) -> RE.Pattern[str]:
    """Compile ``template`` into a regex with one named group per placeholder."""
    chunks: list[str] = []
    placeholder = 0
    for segment in _segments(template):
        if segment is None:
            chunks.append(_field_chunk(placeholder, fields[placeholder]))
            placeholder += 1
        else:
            chunks.append(_literal_to_pattern(segment))
    return RE.compile("".join(chunks))


def _winner(match: RE.Match[str], index: int, branch_names: tuple[str, ...]) -> int:
    """Index of the branch whose pattern produced the field's match."""
    if not branch_names:
        return 0
    for branch, name in enumerate(branch_names):
        if match.group(name) is not None:
            return branch
    raise AssertionError(f"no converter branch matched field {index}")


class Template:
    """A validated, compiled template, ready to scan input."""

    def __init__(self, template: str, fields: tuple[Field, ...]) -> None:
        # Validate up front: converters must be callable and hashable.
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
        self.pattern = _compile(template, fields)
        self._field_names = tuple(f"s{index}" for index in range(len(fields)))
        self._branch_names: tuple[tuple[str, ...], ...] = tuple(
            tuple(
                _branch_group(index, branch) for branch in range(len(field.converters))
            )
            if len(field.converters) > 1
            else ()
            for index, field in enumerate(fields)
        )

    def fullmatch(self, input_value: str) -> tuple[Any, ...]:
        """Scan ``input_value``: match the template and convert each field."""
        match = self.pattern.fullmatch(input_value.strip())
        if match is None:
            raise MatchError(
                f"input {input_value!r} does not match template {self.template!r}",
                input_value=input_value,
                template=self.template,
            )
        # Error offsets are reported against the original input; the strip
        # shift is only computed when a conversion actually fails.
        return self._convert(match, input_value, stripped=True)

    def search(self, input_value: str) -> tuple[Any, ...] | None:
        """Scan ``input_value`` for the first match; ``None`` when not found."""
        match = self.pattern.search(input_value)
        if match is None:
            return None
        return self._convert(match, input_value, stripped=False)

    def findall(self, input_value: str) -> list[tuple[Any, ...]]:
        """Scan ``input_value`` for every non-overlapping match, left to right."""
        return [
            self._convert(match, input_value, stripped=False)
            for match in self.pattern.finditer(input_value)
        ]

    def _convert(
        self, match: RE.Match[str], input_value: str, *, stripped: bool
    ) -> tuple[Any, ...]:
        """Convert one match's fields.

        ``stripped`` marks a match that ran against the stripped input; error
        offsets are then reported against the original input.
        """
        values: list[Any] = []
        for index, (field, name, branch_names) in enumerate(
            zip(self.fields, self._field_names, self._branch_names, strict=True)
        ):
            converter = field.converters[_winner(match, index, branch_names)]
            raw = match.group(name)
            text = raw.strip() if converter.strip else raw
            try:
                values.append(converter.fn(text))
            except Exception as error:
                offset = match.start(name)
                if stripped:
                    offset += len(input_value) - len(input_value.lstrip())
                label = _label(converter)
                raise ConvertError(
                    f"cannot convert field {index + 1} ({text!r}) at offset "
                    f"{offset} using {label}",
                    field=index + 1,
                    offset=offset,
                    text=text,
                    converter=label,
                    input_value=input_value,
                    template=self.template,
                ) from error
        return tuple(values)
