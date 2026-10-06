"""moe_calc: a cute recursive-descent calculator built as a scanf showcase.

The grammar is the classic four-function one::

    expr  := term (('+' | '-') term)*
    term  := unary (('*' | '/') unary)*
    unary := ('-' | '+') unary | atom
    atom  := number | '(' expr ')'

Four scanf-flavoured pieces carry the parser:

* number leaves use competing ``Converter`` branches on one field -- ``int``
  for plain digits, ``float`` for decimal literals, first match wins;
* ``atom`` alternatives (parenthesized group vs plain number) are an ordered
  ``alt`` choice, where only ``MatchError`` -- the soft failure -- falls
  through to the next alternative;
* the unary sign level is an ``alt`` of sign templates as well: ``"+{}"``
  recurses through the fixpoint thunk, ``"-{}"`` negates the recursive
  result, and ``"{}"`` hands the text over to ``atom``;
* parentheses need true recursion, which a regex cannot express, so the whole
  parser is built through the ``recursive`` fixpoint, and each operator level
  splits at its own last top-level operator (see ``_rfind_binary``).

Run it directly for a fixed demo, or with ``--repl`` to chat::

    uv run python example/moe_calc.py
    uv run python example/moe_calc.py --repl
"""

import sys
from collections.abc import Callable
from typing import Annotated

from infinity_parse import Converter, MatchError, ScanError, scanf

type Number = int | float
type Parser = Callable[[str], Number]


class MoeCalcError(ValueError):
    """The expression could not be parsed or evaluated -- said cutely."""


# Competing branches on one field: plain digits stay int, decimal literals
# fall through to the float branch. Branch order decides who wins.
_number = scanf[
    Annotated[
        Number,
        Converter(int, pattern=r"\d+", name="整数"),
        Converter(float, pattern=r"\d+\.\d+", name="小数"),
    ]
]("{}")


def warp_scanf[T, *Ts](s: scanf[T, *Ts]) -> Callable[[str], T]:
    """Adapt a scanf parser into a plain ``Parser``: unwrap its first field."""
    return lambda text: s(text)[0]


def _rfind_binary(text: str, operators: str) -> int | None:
    """Index of the last top-level binary operator taken from ``operators``.

    A ``+``/``-`` right after another operator or after ``(`` is unary, so it
    must not split the expression; every operand is split at a binary one.
    """
    depth = 0
    found: int | None = None
    for index, character in enumerate(text):
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif depth == 0 and character in operators:
            previous = text[:index].rstrip()[-1:]
            if previous and previous not in "(+-*/":
                found = index
    return found


def _inner_of_parens(text: str) -> str | None:
    """Inner text when one pair of parens wraps ``text`` entirely, else None."""
    if not text.startswith("("):
        return None
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return text[1:index] if index == len(text) - 1 else None
    return None


def _apply(operator: str, left: Number, right: Number) -> Number:
    """Evaluate one binary operator, with moe-flavoured division by zero."""
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if right == 0:
            raise MoeCalcError("不能除以零啦! 人家不想变成黑洞 (>_<)")
        return left / right
    raise AssertionError(f"unknown operator: {operator!r}")


def recursive(builder: Callable[[Parser], Parser]) -> Parser:
    """Fixpoint combinator: ``builder`` receives a thunk to the full parser."""

    ref: Parser | None = None

    def thunk(text: str) -> Number:
        assert ref is not None
        return ref(text)

    parser = builder(thunk)
    ref = parser
    return parser


def alt(*parsers: Parser) -> Parser:
    """Ordered choice across parsers; only ``MatchError`` falls through."""

    def parse(text: str) -> Number:
        failure: MatchError | None = None
        for parser in parsers:
            try:
                return parser(text)
            except MatchError as error:
                failure = error
        raise MatchError(f"no alternative matched {text!r}") from failure

    return parse


def build_calc(self: Parser) -> Parser:
    """Build the ``expr`` level; ``self`` recurses into a whole expression."""

    def parse_number(text: str) -> Number:
        return _number(text)[0]

    def parse_group(text: str) -> Number:
        inner = _inner_of_parens(text.strip())
        if inner is None:
            raise MatchError(f"not a parenthesized group: {text!r}")
        return self(inner)

    atom = alt(parse_group, parse_number)

    parse_unary = recursive(
        lambda self: alt(
            warp_scanf(scanf[Annotated[Number, Converter(fn=self)]]("+{}")),
            warp_scanf(
                scanf[Annotated[Number, Converter(fn=lambda text: -self(text))]]("-{}")
            ),
            warp_scanf(scanf[Annotated[Number, Converter(fn=atom)]]("{}")),
        )
    )

    def parse_term(text: str) -> Number:
        index = _rfind_binary(text, "*/")
        if index is None:
            return parse_unary(text)
        return _apply(
            text[index], parse_term(text[:index]), parse_unary(text[index + 1 :])
        )

    def parse_expr(text: str) -> Number:
        index = _rfind_binary(text, "+-")
        if index is None:
            return parse_term(text)
        return _apply(
            text[index], parse_expr(text[:index]), parse_term(text[index + 1 :])
        )

    return parse_expr


_calculate = recursive(build_calc)


def moe_calc(expression: str) -> Number:
    """Evaluate an arithmetic expression, or fail with a ``MoeCalcError``."""
    try:
        return _calculate(expression)
    except ScanError as error:
        # Sign/group branches convert through nested scans, so the engine
        # upgrades any inner failure to ConvertError; recover the original
        # MoeCalcError through __cause__ so nested cases stay cute too.
        cause: BaseException | None = error.__cause__
        while cause is not None and not isinstance(cause, MoeCalcError):
            cause = cause.__cause__
        if cause is not None:
            raise cause from None
        raise MoeCalcError(
            f"喵呜... 人家看不懂这个算式啦: {expression!r} (>_<)"
        ) from error


def _demo() -> None:
    """Evaluate a few fixed expressions, then two cute failures."""
    samples = [
        "1 + 2 * 3",
        "10 - 2 * 3",
        "1 - 2 - 3",
        "(1 + 2) * 3",
        "2 * (3 + 4) - 5",
        "((1 + 2)) * 3",
        "7 / 2",
        "2 * -3",
    ]
    for expression in samples:
        print(f"喵! {expression} = {moe_calc(expression)}")
    for broken in ("1 + * 2", "1 / 0"):
        try:
            moe_calc(broken)
        except MoeCalcError as error:
            print(f"呜... {error}")


def _repl() -> None:
    """Chat with the calculator until EOF or a quit word."""
    print("moe_calc 已上线! 输入算式开始玩耍, 输入 q 退出 (=^_^=)")
    while True:
        try:
            line = input("moe> ")
        except EOFError:
            print()
            break
        if line.strip().casefold() in {"q", "quit", "exit"}:
            print("bye bye~ 记得想人家哦")
            break
        try:
            print(f"= {moe_calc(line)}")
        except MoeCalcError as error:
            print(error)


if __name__ == "__main__":
    if "--repl" in sys.argv[1:]:
        _repl()
    else:
        _demo()
