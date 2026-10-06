"""Strictly typed, ``scanf``-style parsing for Python."""

from infinity_parse.combinators import (
    Parser,
    alt,
    first_field,
    recursive,
    sep_by,
    split_top,
)
from infinity_parse.engine import (
    Converter,
    ConvertError,
    MatchError,
    ScanError,
    Template,
    resolve_field,
)
from infinity_parse.scanner import (
    Scanner,
    scan,
    scanall,
    search,
)

__all__: list[str] = [
    "ConvertError",
    "Converter",
    "MatchError",
    "Parser",
    "ScanError",
    "Scanner",
    "Template",
    "alt",
    "first_field",
    "recursive",
    "resolve_field",
    "scan",
    "scanall",
    "search",
    "sep_by",
    "split_top",
]
