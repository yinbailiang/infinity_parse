r"""Type-safe, ``scanf``-style string parsing.

Supply one converter type per ``{}`` placeholder as class type arguments, then
the template and the input string as call arguments::

    from infinity_parse import scan

    a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
    # a=1 (int), b=2.5 (float), c="hello" (str)

Parsers are reusable. Fields accept per-field ``Converter`` specs and built-in
defaults (containers via ``ast.literal_eval``, ``bool`` literals); see the
project README for the full guide -- usage, semantics and examples.
"""

import types
from typing import Annotated, Any, TypeAliasType, cast, get_args, get_origin

from infinity_parse.engine import (
    Converter,
    ConvertError,
    Field,
    MatchError,
    ScanError,
    Template,
    resolve_field,
)

__all__: list[str] = [
    "ConvertError",
    "Converter",
    "MatchError",
    "ScanError",
    "Scanner",
    "scan",
    "scanall",
    "search",
]


def flatten_annotated(meta: Any) -> tuple[Any, list[Any]]:
    """Flatten nested ``Annotated`` wrappers and PEP 695 aliases"""
    if isinstance(meta, TypeAliasType):
        return flatten_annotated(meta.__value__)
    if get_origin(meta) is not Annotated:
        return meta, []
    args = get_args(meta)
    base, metadata = flatten_annotated(args[0])
    return base, [*metadata, *args[1:]]


def build_field(meta: Any) -> Field:
    """Extract one declaration's Converter specs and resolve them via the engine."""
    declared, metadata = flatten_annotated(meta)
    converters: list[Converter[Any]] = [
        cast(Converter[Any], item) for item in metadata if isinstance(item, Converter)
    ]
    return resolve_field(declared, converters)


class Scanner[*Meta]:
    """Typed scanner over ``{}`` fields.

    Call ``scan`` for a full match, ``search`` for the first match, or
    ``scanall`` for every match; instances expose the same as ``fullmatch`` /
    ``search`` / ``findall`` methods.
    """

    def __init__(self, template: str, _engine: Template | None = None) -> None:
        # Built through subscription (``scan[...]``); calling directly is a misuse.
        if _engine is None:
            raise TypeError(
                "Scanner requires at least one converter type, e.g. Scanner[int]('{}')"
            )
        self._engine = _engine

    @classmethod
    def __class_getitem__(cls, item: Any) -> Any:
        """Bind the field metas; called by ``Scanner[...]``."""
        metas = cast(tuple[Any, ...], item if isinstance(item, tuple) else (item,))
        if not metas:
            raise TypeError(
                "Scanner requires at least one converter type, e.g. Scanner[int]('{}')"
            )
        return _ScannerAlias(cls, metas)

    def fullmatch(self, input_value: str) -> tuple[*Meta]:
        """Match the whole input."""
        return self._engine.fullmatch(input_value)

    def search(self, input_value: str) -> tuple[*Meta] | None:
        """First match anywhere, or ``None``."""
        return self._engine.search(input_value)

    def findall(self, input_value: str) -> list[tuple[*Meta]]:
        """All non-overlapping matches, left to right."""
        return self._engine.findall(input_value)


class _ScannerAlias(types.GenericAlias):
    """Subclass of ``types.GenericAlias`` carrying the field metas."""

    def __call__(self, template: str) -> Any:
        origin = cast(Any, self.__origin__)
        fields: tuple[Field, ...] = tuple(build_field(meta) for meta in self.__args__)
        instance = origin(template, Template(template, fields))
        instance.__orig_class__ = self
        return instance


class scan[*Meta](Scanner[*Meta]):
    """Callable scanner: calling it is ``fullmatch``."""

    def __call__(self, input_value: str) -> tuple[*Meta]:
        return super().fullmatch(input_value)


class scanall[*Meta](Scanner[*Meta]):
    """Callable scanner: calling it is ``findall``."""

    def __call__(self, input_value: str) -> list[tuple[*Meta]]:
        return super().findall(input_value)


class search[*Meta](Scanner[*Meta]):
    """Callable scanner: calling it is ``search``."""

    def __call__(self, input_value: str) -> tuple[*Meta] | None:
        return super().search(input_value)
