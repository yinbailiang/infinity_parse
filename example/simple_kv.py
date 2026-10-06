import json
from typing import Annotated

from infinity_parse import Converter, ScanError, scan

_ESCAPED = r'"(?:[^"\\]|\\.)*"'

type Key = Annotated[
    str,
    Converter(json.loads, pattern=_ESCAPED, name="escaped key"),
    Converter(str, pattern=r"[^=\s]+", name="bare key"),
]

type Value = Annotated[
    str,
    Converter(json.loads, pattern=_ESCAPED, name="escaped value"),
    Converter(str, pattern=r".*", name="bare value"),
]

_line = scan[Key, Value]("{}={}")


def parse_kv(text: str) -> dict[str, str]:
    """解析 `key=value` 行, 跳过空行和 `#` 注释。"""
    result: dict[str, str] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            key, value = _line(stripped)  # 静态类型: tuple[str, str]
        except ScanError as error:
            raise ValueError(f"line {lineno}: {error}") from error
        result[key] = value
    return result
