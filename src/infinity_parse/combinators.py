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
        raise MatchError(
            f"no alternative matched {text!r}", input_value=text
        ) from failure

    return parse


def recursive[T](builder: Callable[[Parser[T]], Parser[T]]) -> Parser[T]:
    """Fixpoint combinator: ``builder`` receives a thunk to the finished parser.

    Nesting is bounded by the interpreter recursion limit (roughly 300-350
    levels for typical grammars with default settings), so very deep grammars
    may need ``sys.setrecursionlimit``.
    """

    ref: Parser[T] | None = None

    def thunk(text: str) -> T:
        assert ref is not None, "recursive() thunk called before parser was built"
        return ref(text)

    parser = builder(thunk)
    ref = parser
    return parser


def split_top(separator: str, delimiters: tuple[str, str]) -> Parser[list[str]]:
    """Split at top-level ``separator``; ``delimiters`` protect inner ones.

    ``delimiters`` is a pair of character sets (open, close): any character
    from the open set increases nesting and any from the close set decreases
    it. Only the characters you pass are protected — e.g. ``("[{", "}]")``
    protects ``[]`` and ``{}``, but not parentheses.
    """

    def spliter(text: str) -> list[str]:
        parts: list[str] = []
        depth = 0
        start = 0
        for index, character in enumerate(text):
            if character in delimiters[0]:
                depth += 1
            elif character in delimiters[1]:
                depth -= 1
            elif character == separator and depth == 0:
                parts.append(text[start:index])
                start = index + 1
        parts.append(text[start:])
        return parts

    return spliter


def sep_by[T](parser: Parser[T], spliter: Parser[list[str]]) -> Parser[list[T]]:
    """Parse the members produced by ``spliter``, one ``parser`` each."""

    def parse(text: str) -> list[T]:
        return [parser(member) for member in spliter(text)]

    return parse


def first_field[T, *Ts](parser: Parser[tuple[T, *Ts]]) -> Parser[T]:
    """Adapt a scanner: unwrap the first field of its result tuple."""

    def parse(text: str) -> T:
        return parser(text)[0]

    return parse
