"""Worked examples for ``scan``: per-field converter specs, plus a recursive
scanner built from the library's fixpoint combinator.
"""

import json
from typing import Annotated, Any

from infinity_parse import (
    Converter,
    Parser,
    ScanError,
    first_field,
    recursive,
    scan,
    sep_by,
)

parse = scan[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
    Annotated[float, Converter(float, pattern=r"[-+]?\d+\.\d+", name="score")],
]("age={} name={} score={}")
# 或者更简单 scan[int, str, float]("age={} name={} score={}")
# 但没有自定义的转换器和模式
age, name, score = parse('age=42 name="kim" score=98.5')
print(age, name, score)  # 42 "kim" 98.5


# Converter also covers custom parsing needs (e.g. JSON instead of Python literals):
parse_json = scan[Annotated[dict[str, str], Converter[dict[str, str]](json.loads)]](
    "{}"
)
print(parse_json('{"key": "value"}'))  # ({"key": "value"},)


# Competing branches: first match wins; failures abort the scan.
parse_number = scan[
    Annotated[
        int | float,
        Converter(int, pattern=r"[-+]?\d+"),
        Converter(float, pattern=r"[-+]?\d+\.\d+"),
    ]
]("{}")
print(parse_number("42"))  # (42,)
print(parse_number("3.14"))  # (3.14,)


# Escape-aware string field: json.loads decodes; bad escapes raise ConvertError.
parse_escaped = scan[
    Annotated[str, Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="name")]
]("{}")
print(parse_escaped(r'"kim \"the fox\""'))  # ('kim "the fox"',)


def build_node(self: Parser[Any]) -> Parser[Any]:
    """One scanner per node kind, as competing ``Converter`` branches on a field."""

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

    node = scan[
        Annotated[
            Any,
            Converter(to_object, pattern=r"\{.+\}", name="object"),
            Converter(to_array, pattern=r"\[.+\]", name="array"),
            Converter(to_atom, pattern=r"^\w+$", name="atom"),
        ]
    ]("{}")

    return first_field(node)


src = """{a:[[{c:1}, {d:2}], [{c:3}, {d:4}]]}"""

node = recursive(build_node)
result = node(src)
print(result)  # {'a': [[{'c': 1}, {'d': 2}], [{'c': 3}, {'d': 4}]]}

# Nested failures chain through ``__cause__``.
try:
    node("{a:@}")
except ScanError as error:
    print("error:", error)
    print("cause:", error.__cause__)
