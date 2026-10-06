"""Worked examples for ``scanf``: per-field converter specs, plus a recursive
scanner built from a fixpoint combinator.
"""

import json
from collections.abc import Callable
from typing import Annotated, Any

from infinity_parse import Converter, MatchError, ScanError, scanf

parse = scanf[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
    Annotated[float, Converter(float, pattern=r"[-+]?\d+\.\d+", name="score")],
]("age={} name={} score={}")
# 或者更简单 scanf[int, str, float]("age={} name={} score={}")
# 但没有自定义的转换器和模式
age, name, score = parse('age=42 name="kim" score=98.5')
print(age, name, score)  # 42 "kim" 98.5


# Converter also covers custom parsing needs (e.g. JSON instead of Python literals):
parse_json = scanf[Annotated[dict[str, str], Converter[dict[str, str]](json.loads)]](
    "{}"
)
print(parse_json('{"key": "value"}'))  # ({"key": "value"},)


# Several Converter specs on one field compete in declaration order: the first
# branch whose pattern matches wins, and a failing converter aborts the scan
# instead of falling through to a later branch.
parse_number = scanf[
    Annotated[
        int | float,
        Converter(int, pattern=r"[-+]?\d+"),
        Converter(float, pattern=r"[-+]?\d+\.\d+"),
    ]
]("{}")
print(parse_number("42"))  # (42,)
print(parse_number("3.14"))  # (3.14,)


# Escape-aware string fields: `(?:[^"\\]|\\.)*` lets `\"` stay inside the
# string, and json.loads decodes the captured text -- malformed escapes abort
# with ConvertError instead of passing silently.
parse_escaped = scanf[
    Annotated[str, Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="name")]
]("{}")
print(parse_escaped(r'"kim \"the fox\""'))  # ('kim "the fox"',)


def recursive(builder: Any) -> Any:
    """Fixpoint: ``builder`` gets a thunk that calls the finished scanner."""
    ref: Any = None

    def thunk(text: str) -> Any:
        return ref(text)

    parser = builder(thunk)
    ref = parser
    return parser


def split_top(text: str, separator: str) -> list[str]:
    """Split at top-level ``separator`` characters; brackets protect inner ones.

    This is the one piece templates cannot express: regular expressions have no
    notion of balanced delimiters.
    """
    parts: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(text):
        if character in "{[":
            depth += 1
        elif character in "}]":
            depth -= 1
        elif character == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def alt(*parsers: Callable[[str], Any]) -> Callable[[str], Any]:
    """Ordered choice across *separate* parsers.

    Keep this for alternatives that span different templates or several fields
    (e.g. ``"let {} = {}"`` vs ``"print {}"``). Alternatives confined to one
    template need no combinator: ``scanf`` already competes the ``Converter``
    specs on a field in declaration order, with the same rule as below (see
    ``build_node``).

    Only ``MatchError`` (the soft failure) falls through to the next
    alternative; a branch that matched but failed to convert raises
    ``ConvertError``, aborting the choice so its diagnostics are never
    swallowed.
    """

    def parse(text: str) -> Any:
        failure: MatchError | None = None
        for parser in parsers:
            try:
                return parser(text)
            except MatchError as error:
                failure = error
        raise MatchError(f"no alternative matched {text!r}") from failure

    return parse


def sep_by(
    parser: Callable[[str], Any], separator: str = ","
) -> Callable[[str], list[Any]]:
    """Parse top-level ``separator``-separated members, one ``parser`` each."""

    def parse(text: str) -> list[Any]:
        return [parser(member) for member in split_top(text, separator)]

    return parse


def build_node(self: Any) -> Any:
    """One scanner per node kind -- as competing branches on a single field.

    Object, array and atom are ``Converter`` specs on one field: the first
    branch whose pattern matches wins, and a converter failure aborts the scan
    -- the field-level counterpart of ``alt``. Delimiters live in the branch
    patterns (``\\{.+\\}`` / ``\\[.+\\]``), so each converter strips the shell
    before parsing the inside. ``sep_by`` turns the member lists into grammar,
    and every converter consumes one layer before recursing so the fixpoint
    terminates.
    """

    def parse_pair(member: str) -> tuple[str, Any]:
        key, _, raw = member.partition(":")
        return key.strip(), self(raw)

    pairs = sep_by(parse_pair)
    members = sep_by(self)

    def to_object(text: str) -> Any:
        return dict(pairs(text[1:-1]))

    def to_array(text: str) -> Any:
        return members(text[1:-1])

    def to_atom(text: str) -> Any:
        return int(text) if text.isdigit() else text

    node = scanf[
        Annotated[
            Any,
            Converter(to_object, pattern=r"\{.+\}", name="object"),
            Converter(to_array, pattern=r"\[.+\]", name="array"),
            Converter(to_atom, pattern=r"^\w+$", name="atom"),
        ]
    ]("{}")

    def parse_node(text: str) -> Any:
        """Scan one node and unwrap its single field."""
        return node(text)[0]

    return parse_node


src = """{a:[[{c:1}, {d:2}], [{c:3}, {d:4}]]}"""

node = recursive(build_node)
result = node(src)
print(result)  # {'a': [[{'c': 1}, {'d': 2}], [{'c': 3}, {'d': 4}]]}

# Nested failures wrap layer by layer: each "cannot convert field ... using
# object" chains to the error from the level below through ``__cause__``.
try:
    node("{a:@}")
except ScanError as error:
    print("error:", error)
    print("cause:", error.__cause__)
