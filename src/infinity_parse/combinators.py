"""Parser combinators: ordered choice, recursion and separated lists."""

from collections.abc import Callable

from infinity_parse.engine import MatchError

type Parser[T] = Callable[[str], T]


def alt[T](*parsers: Parser[T]) -> Parser[T]:
    """Ordered choice: the first parser that does not raise ``MatchError`` wins."""

    def parse(text: str) -> T:
        failure: MatchError | None = None
        for parser in parsers:
            try:
                return parser(text)
            except MatchError as error:
                failure = error
        raise MatchError(f"no alternative matched {text!r}") from failure

    return parse


def recursive[T](builder: Callable[[Parser[T]], Parser[T]]) -> Parser[T]:
    """Fixpoint combinator: ``builder`` receives a thunk to the finished parser."""

    ref: Parser[T] | None = None

    def thunk(text: str) -> T:
        assert ref is not None, "recursive() thunk called before parser was built"
        return ref(text)

    parser = builder(thunk)
    ref = parser
    return parser


def split_top(text: str, separator: str) -> list[str]:
    """Split at top-level ``separator`` characters; brackets protect inner ones."""
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


def sep_by[T](parser: Parser[T], separator: str = ",") -> Parser[list[T]]:
    """Parse top-level ``separator``-separated members, one ``parser`` each."""

    def parse(text: str) -> list[T]:
        return [parser(member) for member in split_top(text, separator)]

    return parse


def first_field[T, *Ts](parser: Parser[tuple[T, *Ts]]) -> Parser[T]:
    """Adapt a scanner: unwrap the first field of its result tuple."""

    def parse(text: str) -> T:
        return parser(text)[0]

    return parse
