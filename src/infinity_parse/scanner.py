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

import ast
import types
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Annotated, Any, TypeAliasType, cast, get_args, get_origin

from infinity_parse.engine import (
    Converter,
    ConvertError,
    Field,
    MatchError,
    ScanError,
    Template,
)

__all__: list[str] = [
    "ConvertError",
    "Converter",
    "MatchError",
    "OneOf",
    "ScanError",
    "Scanner",
    "resolve_field",
    "scan",
    "scanall",
    "search",
]


@dataclass(frozen=True, repr=False)
class _OneOfSpec:
    """The runtime value of ``OneOf[...]``: competing converter branches."""

    converters: tuple[Converter[Any], ...]

    def __repr__(self) -> str:
        inner = ", ".join(repr(converter) for converter in self.converters)
        return f"OneOf[{inner}]"


class OneOf:
    """Packs competing ``Converter`` branches into one field spec.

    ``Annotated[T, OneOf[C1, C2]]`` competes the packed branches in
    declaration order; bare multiple ``Converter`` specs are rejected.
    """

    def __init__(self) -> None:
        # Built through subscription (``OneOf[C1, C2]``); calling directly is misuse.
        raise TypeError("OneOf is used through subscription: OneOf[C1, C2]")

    @classmethod
    def __class_getitem__(cls, item: Any) -> _OneOfSpec:
        """Pack the given ``Converter`` instances; called by ``OneOf[...]``."""
        converters = cast(tuple[Any, ...], item if isinstance(item, tuple) else (item,))
        if not converters:
            raise TypeError("OneOf requires at least one Converter")
        for converter in converters:
            if not isinstance(converter, Converter):
                raise TypeError(f"OneOf accepts Converter instances, got {converter!r}")
        return _OneOfSpec(converters=tuple(converters))


def _has_spec(items: Iterable[Any]) -> bool:
    """Whether ``items`` contains a spec (a ``Converter`` or a ``OneOf``)."""
    return any(isinstance(item, Converter | _OneOfSpec) for item in items)


def flatten_annotated(meta: Any) -> tuple[Any, list[Any]]:
    """Flatten nested ``Annotated`` wrappers and PEP 695 aliases."""
    if isinstance(meta, TypeAliasType):
        return flatten_annotated(meta.__value__)
    if get_origin(meta) is not Annotated:
        return meta, []
    args = get_args(meta)
    base, metadata = flatten_annotated(args[0])
    return base, [*metadata, *args[1:]]


def _literal_converter(origin: type[Any]) -> Callable[[str], Any]:
    return lambda text: origin(ast.literal_eval(text))


_BOOL_VALUES = {"true": True, "false": False, "1": True, "0": False}


def _bool_converter(text: str) -> bool:
    value = _BOOL_VALUES.get(text.casefold())
    if value is None:
        raise ValueError(f"cannot parse {text!r} as bool")
    return value


# Built-in defaults, keyed by type object (not by name).
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


def _default_branch(declared: Any) -> Converter[Any]:
    """Default converter branch for a declared type without ``Converter`` specs."""
    branch: Converter[Any] = Converter(
        fn=_default_converter(declared) or declared,
        name=_converter_name(declared),
    )
    return branch


def resolve_field(declared: Any, convs: list[Converter[Any]]) -> Field:
    """Resolve one field's meta into its converter branches (meta -> converters)."""
    if convs:
        return Field(converters=tuple(convs))
    return Field(converters=(_default_branch(declared),))


def _is_union(meta: Any) -> bool:
    """Whether ``meta`` is a union (PEP 604 and ``typing.Union`` are one in 3.14)."""
    return get_origin(meta) is types.UnionType


def _join_union(members: list[Any]) -> Any:
    """Rebuild one union from peeled member types (``|`` keeps the union flat)."""
    joined: Any = members[0]
    for member in members[1:]:
        joined = joined | member
    return joined


def _has_specs(meta: Any) -> bool:
    """Whether ``meta`` carries explicit specs (default branches excluded)."""
    base, metadata = flatten_annotated(meta)
    if _has_spec(metadata):
        return True
    return _is_union(base) and any(_has_specs(member) for member in get_args(base))


def _collect_specs(metadata: Iterable[Any]) -> list[Converter[Any]]:
    """Collect one layer's branches: one ``Converter`` or one ``OneOf``."""
    converters: list[Converter[Any]] = []
    specs = 0
    for item in metadata:
        if isinstance(item, Converter):
            specs += 1
            converters.append(cast(Converter[Any], item))
        elif isinstance(item, _OneOfSpec):
            specs += 1
            converters.extend(item.converters)
    if specs > 1:
        raise ValueError(
            "multiple Converter specs on one field; pack competing branches "
            "in OneOf[*Converter], e.g. Annotated[T, OneOf[C1, C2]]"
        )
    return converters


def normalize_meta(meta: Any) -> tuple[Any, list[Converter[Any]]]:
    """Flatten annotations; expand union members into converter branches.

    ``Annotated[int, C1] | Annotated[float, C2]`` normalizes to ``int | float``
    with ``[C1, C2]``; members without specs contribute a default branch.
    Specs on an ``Annotated`` wrapping the whole union bind it as one branch
    group, unless members carry their own specs (rejected as ambiguous).
    Competing branches must be packed in ``OneOf``; other metadata is ignored.
    """
    base, metadata = flatten_annotated(meta)
    convs = _collect_specs(metadata)
    if not _is_union(base):
        return base, convs
    if convs:
        if any(_has_specs(member) for member in get_args(base)):
            raise ValueError(
                "Converter specs on an Annotated wrapping a union cannot be "
                "combined with member specs; attach each spec to its own member"
            )
        return base, convs
    members: list[Any] = []
    for member in get_args(base):
        member_base, member_convs = normalize_meta(member)
        members.append(member_base)
        if member_convs:
            convs.extend(member_convs)
        else:
            convs.append(_default_branch(member_base))
    return _join_union(members), convs


def build_field(meta: Any) -> Field:
    """Extract one declaration's Converter specs (unions included) and resolve them."""
    declared, converters = normalize_meta(meta)
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
