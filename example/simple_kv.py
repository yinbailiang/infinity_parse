import json
from typing import Annotated

from infinity_parse import Converter, OneOf, ScanError, scan

_ESCAPED = r'"(?:[^"\\]|\\.)*"'

type Key = Annotated[
    str,
    OneOf[
        Converter(json.loads, pattern=_ESCAPED, name="escaped key"),
        Converter(str, pattern=r"[^=\s]+", name="bare key"),
    ],
]

type Value = Annotated[
    str,
    OneOf[
        Converter(json.loads, pattern=_ESCAPED, name="escaped value"),
        Converter(str, pattern=r".*", name="bare value"),
    ],
]

parse_line = scan[Key, Value]("{} = {}")


def parse_kv(text: str) -> dict[str, str]:
    """解析 `key=value` 行, 跳过空行和 `#` 注释。"""
    result: dict[str, str] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            key, value = parse_line(stripped)
        except ScanError as error:
            raise ValueError(f"line {lineno}: {error}") from error
        result[key] = value
    return result


print(
    parse_kv("""# comment
foo = bar
"baz" = "qux"
# another comment
"escaped key" = "escaped value"
""")
)  # {'foo': 'bar', 'baz': 'qux', 'escaped key': 'escaped value'}
