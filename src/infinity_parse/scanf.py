r"""Type-safe, ``scanf``-style string parsing.

Supply one converter type per ``{}`` placeholder as class type arguments, then
the template and the input string as call arguments::

    from infinity_parse import scanf

    a, b, c = scanf[int, float, str]("{} {} {}")("1 2.5 hello")
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

__all__ = ["ConvertError", "Converter", "MatchError", "ScanError", "scanf"]


def flatten_annotated(meta: Any) -> tuple[Any, list[Any]]:
    """Flatten nested ``Annotated`` wrappers and PEP 695 aliases; metadata
    ordered deep to shallow (which is also the order converter branches
    compete in)."""
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


class scanf[*Meta]:
    """Typed ``scanf``: ``scanf[Meta1, Meta2, ...](template)(input_value)``.

    Each ``Meta`` declares one field -- a converter type, or
    ``Annotated[converter, Converter(...)]`` for per-field configuration --
    and determines the corresponding result element type. Several ``Converter``
    specs on one field compete in order: the first matching branch wins. The
    template and the input string are call arguments. Parsers are reusable.

    The converter setup is validated eagerly when the parser is constructed:
    non-callable converters and placeholder/converter-count mismatches raise
    immediately.
    """

    _engine: Template

    def __init__(self, template: str, _engine: Template | None = None) -> None:
        # Parsers are built through ``scanf[...]`` (see _ScanfAlias), which
        # passes the ready engine in; direct construction is a misuse.
        if _engine is None:
            raise TypeError(
                "scanf requires at least one converter type, e.g. scanf[int]('{}')"
            )
        self._engine = _engine

    @classmethod
    def __class_getitem__(cls, item: Any) -> Any:
        """Bind the field metas; see the class docstring.

        Type checkers ignore this hook for generic classes and keep treating
        ``scanf[int, float]`` as a specialization. At runtime it returns a
        ``types.GenericAlias`` subclass carrying the metas; calling that alias
        with the template is what validates and builds the parser.
        """
        metas = cast(tuple[Any, ...], item if isinstance(item, tuple) else (item,))
        if not metas:
            raise TypeError(
                "scanf requires at least one converter type, e.g. scanf[int]('{}')"
            )
        return _ScanfAlias(cls, metas)

    def __call__(self, input_value: str) -> tuple[*Meta]:
        """Parse ``input_value``."""
        return self._engine.scan(input_value)


class _ScanfAlias(types.GenericAlias):
    """Subclass of ``types.GenericAlias`` produced by ``scanf[...]``.

    The field metas travel in the alias itself (``__args__``). Calling the
    alias with the template is where both sides meet: it resolves each meta
    into its converter, validates the configuration and constructs the parser,
    setting ``__orig_class__`` the way typing would.
    """

    def __call__(self, template: str) -> Any:
        origin = cast(Any, self.__origin__)
        fields: tuple[Field, ...] = tuple(build_field(meta) for meta in self.__args__)
        instance = origin(template, Template(template, fields))
        instance.__orig_class__ = self
        return instance
