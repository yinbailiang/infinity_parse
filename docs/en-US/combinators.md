# Combinators

## Overview

The `combinators` module provides five composition primitives that build larger
parsers out of scanners and plain callables. The core abstraction:

```python
type Parser[T] = Callable[[str], T]
```

A scanner is itself a `Callable[[str], tuple[...]]` — pair it with `first_field` to
plug it into the combinators. Every combinator treats only `MatchError` (no match)
as "try the next option"; all other exceptions propagate unchanged.

```python
from infinity_parse import alt, first_field, scan

value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
value('"hi"')  # 'hi'
value("hi")  # 'hi'
```

---

## alt — Ordered Choice

```python
def alt[T](*parsers: Parser[T]) -> Parser[T]
```

Tries the parsers in order and returns the first result that does not raise
`MatchError`:

- Only `MatchError` triggers "next one"; `ConvertError` and friends abort
  immediately (a hard failure is never swallowed).
- When all parsers fail, raises `MatchError("no alternative matched ...")` with
  `__cause__` pointing at the last failure.

```python
from infinity_parse import ConvertError, MatchError, alt, scan

value = alt(scan[int]("x={}"), scan[int]("y={}"))
value("z=1")  # MatchError: no alternative matched 'z=1'

strict = alt(scan[int]("{}"), scan[str]("{}"))
strict("abc")  # ConvertError — the int branch matched but failed to convert;
# it does not fall back to str
```

## recursive — Fixpoint (Recursion)

```python
def recursive[T](builder: Callable[[Parser[T]], Parser[T]]) -> Parser[T]
```

`builder` receives a thunk pointing at the final parser, which lets you build
self-referential grammars:

```python
from infinity_parse import MatchError, Parser, alt, first_field, recursive, scan


def wrapped(build: Parser[str]) -> Parser[str]:
    def group(text: str) -> str:
        if not (text.startswith("(") and text.endswith(")")):
            raise MatchError(f"not wrapped: {text!r}")
        return build(text[1:-1])

    return alt(group, first_field(scan[str]("{}")))


parse = recursive(wrapped)
parse("(((x)))")  # 'x'
parse("x")  # 'x'
```

## split_top — Top-Level Splitting

```python
def split_top(separator: str, delimiters: tuple[str, str]) -> Parser[list[str]]
```

Splits a string at top-level `separator` characters; `delimiters` (the open and
close character sets) protect separators inside nested text. Returns raw pieces
(no stripping, no parsing):

```python
from infinity_parse import split_top

split_commas = split_top(",", ("[{", "}]"))
split_commas("1, [2, 3], {4, 5}")  # ['1', ' [2, 3]', ' {4, 5}']
```

- Depth is counted per character: any character in the open set `+1`, any in the
  close set `-1`.
- The separator only splits at depth 0; there is no quote awareness.
- Empty input returns `['']`.

## sep_by — Separated Lists

```python
def sep_by[T](parser: Parser[T], spliter: Parser[list[str]]) -> Parser[list[T]]
```

First splits with `spliter` (usually from `split_top`), then applies `parser` to
each piece:

```python
from infinity_parse import first_field, scan, sep_by, split_top

split_commas = split_top(",", ("[{", "}]"))
numbers = sep_by(first_field(scan[int]("{}")), split_commas)
numbers("1, 2, 3")  # [1, 2, 3]
```

## first_field — Adapting Scanners

```python
def first_field[T, *Ts](parser: Parser[tuple[T, *Ts]]) -> Parser[T]
```

Adapts a "scanner that returns a tuple" into a "plain parser returning its first
field", so it can sit inside `alt` / `sep_by` / `recursive`:

```python
value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
```

## A Larger Composition

`example/example.py` builds a recursive node parser from these primitives: each
node competes as several patterned branches (object / array / atom), and child
nodes recurse through the `recursive` thunk:

```python
# Excerpt from example/example.py
def build_node(self: Parser[Any]) -> Parser[Any]:
    def parse_pair(member: str) -> tuple[str, Any]:
        key, _, raw = member.partition(":")
        return key.strip(), self(raw)

    split_commas = split_top(",", ("[{", "}]"))
    pairs = sep_by(parse_pair, split_commas)
    members = sep_by(self, split_commas)
    ...
    node = scan[
        Annotated[
            Any,
            OneOf[
                Converter(to_object, pattern=r"\{.+\}", name="object"),
                Converter(to_array, pattern=r"\[.+\]", name="array"),
                Converter(to_atom, pattern=r"^\w+$", name="atom"),
            ],
        ]
    ]("{}")

    return first_field(node)
```

Fully runnable versions live in the repository: `example/example.py`,
`example/moe_calc.py` and `example/dice_catgirl.py`.

## Notes

- Combinators distinguish only "`MatchError` = no match" from "any other exception =
  hard failure"; a converter's `ConvertError` passes through `alt` by design.
- The `recursive` thunk is only called after `builder` has returned; calling it
  earlier trips an `AssertionError`.
- `split_top` does not trim whitespace: in practice member parsers absorb it
  (e.g. `first_field(scan[int]("{}"))` strips captured fields).
- Combinators process whatever string they are given; whether trailing text is
  acceptable is up to your parser — combinators do not enforce a full match
  (`scan` does that itself).
