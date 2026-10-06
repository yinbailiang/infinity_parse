# infinity_parse

Type-safe, `scanf`-style string parsing for Python 3.14+.
Distributed and imported as `infinity_parse`.

Supply one converter type per `{}` placeholder as class type arguments, then
the template and the input string as call arguments:

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
# a=1 (int), b=2.5 (float), c="hello" (str)
```

Parsers are reusable:

```python
parse_pair = scan[int, int]("{} {}")
parse_pair("7 8")  # (7, 8)
```

## Built-in converters

Built-in generic containers (`dict`, `list`, `tuple`, `set` and `frozenset`)
are parsed as Python literals via `ast.literal_eval`, and `bool` accepts
`true` / `false` / `1` / `0` (case-insensitive):

```python
from infinity_parse import scan

scan[bool]("{}")("true")  # (True,)
scan[list[int]]("{}")("[1, 2, 3]")  # ([1, 2, 3],)
```

For JSON-specific syntax (`true`, `false`, `null`) or any custom conversion,
attach a `Converter` spec:

```python
import json
from typing import Annotated

from infinity_parse import Converter, scan

parse_json = scan[Annotated[dict[str, str], Converter(json.loads)]]("{}")
parse_json('{"key": "value"}')  # ({"key": "value"},)
```

## Per-field configuration

Per-field configuration rides along as `Converter` metadata inside a
`typing.Annotated` converter: a conversion callable, a capture pattern, a
strip flag, `re` flags and a label:

```python
from typing import Annotated

from infinity_parse import Converter, scan

parse = scan[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
]("age={} name={}")
parse('age=42 name="kim"')  # (42, '"kim"')
```

`typing.Annotated` wrappers around converters are stripped; their metadata is
ignored unless it contains a `Converter` spec. Several specs on one field
compete in declaration order: each branch carries its own pattern, the first
branch whose pattern matches wins, and if its converter then fails the whole
scan fails — a failing converter never falls back to a later branch.

Converters can also travel in a PEP 695 `type` alias; aliases are expanded at
runtime exactly as type checkers expand them statically — chains included, and
plain aliases (`type MyInt = int`) pass through as well:

```python
from typing import Annotated

from infinity_parse import Converter, scan

type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,)
```

### Escaped strings

A quoted-string field can be made escape-aware by extending its pattern; the
converter then decodes the captured text:

```python
import json
from typing import Annotated

from infinity_parse import Converter, scan

parse_name = scan[
    Annotated[str, Converter(json.loads, pattern=r'"(?:[^"\\]|\\.)*"', name="name")]
]("{}")
parse_name(r'"kim \"the fox\""')  # ('kim "the fox"',)
parse_name(r'"C:\\path\\to\\file"')  # ('C:\\path\\to\\file',)
```

`(?:[^"\\]|\\.)*` treats `\"` as an escape pair, so the string only ends at an
unescaped quote. `json.loads` decodes the captured text and rejects malformed
escapes with a hard `ConvertError` (never silently).

## Curated types

`infinity_parse.parse_types` ships ready-made converters for common text
shapes, mirroring the `std::scan`-style format specifiers:

```python
from infinity_parse import parse_types as t
from infinity_parse import scan

scan[t.Int, t.SimpleDate]("{} {}")("42 2024-01-15")  # (42, date(2024, 1, 15))
scan[t.Percent]("{}")("12.5%")  # (0.125,)
scan[t.AmPmTime]("{}")("10:21:36 PM")  # (time(22, 21, 36),)
```

The set covers character classes (`t.Letters`, `t.Word`, ...), ISO 8601 /
RFC 2822 / ctime / HTTP-log / syslog date-times, thousands-separated integers
(`t.CommaInt`), percents, hexadecimal / binary / octal integers, floats and
`Decimal`. One caveat: `t.Whitespace` keeps raw spaces, but `scan` strips the
whole input first -- whitespace-only input needs `scanall` / `search`.

## Combining parsers

`infinity_parse.combinators` builds larger parsers out of scanners and plain
callables (all re-exported from the package root):

* `alt(*parsers)` -- ordered choice; only `MatchError` (no match) falls
  through, while a conversion failure aborts.
* `recursive(builder)` -- fixpoint for grammars that nest.
* `sep_by(parser, separator=",")` / `split_top(text, separator)` -- top-level
  separated lists; brackets protect inner separators.
* `first_field(parser)` -- adapt a scanner into a plain `Parser[T]` (a
  `Callable[[str], T]`), so it can sit inside the others.

```python
from infinity_parse import alt, first_field, scan, sep_by

value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
value('"hi"')  # 'hi'
value("hi")  # 'hi'

numbers = sep_by(first_field(scan[int]("{}")))
numbers("1, 2, 3")  # [1, 2, 3]
```

`example/example.py` and `example/moe_calc.py` build their recursive grammars
with these primitives.

## Template semantics

Each `{}` captures with the default `.+?` pattern:

* non-empty: at least one character;
* single-line: never matches a newline;
* lazy: takes the shortest text that still lets the rest of the template match.

A `Converter` spec can replace the pattern per field.

Whitespace runs in the template match any whitespace run in the input, and
surrounding whitespace of the input (and of each captured field) is ignored.
Literal braces in a template are written `{{` and `}}`; a single brace is an
error.

### Matching modes

The same template can be matched in three `re`-style modes, as callable
entry points -- `scan`, `search` and `scanall` -- or as the `fullmatch`,
`search` and `findall` methods of a base `Scanner` instance:

* `scan` -- the template must cover the whole (stripped) input; otherwise
  `MatchError` is raised.
* `search` -- the first match anywhere in the input, or `None` when the
  template does not match.
* `scanall` -- every non-overlapping match, left to right, as a list of field
  tuples; empty when there is no match.

`search` and `scanall` scan the input as-is (no outer strip), and a converter
failure aborts with a hard `ConvertError`, exactly like `scan`:

```python
from typing import Annotated

from infinity_parse import Converter, scan, scanall, search

Number = Annotated[int, Converter(int, pattern=r"\d+")]

scan[Number]("{}")("42")  # (42,)
search[Number]("{}")("answer 42")  # (42,)
scanall[Number]("{}")("1 2 3")  # [(1,), (2,), (3,)]
```

## Development

```bash
uv sync --extra dev
uv run pre-commit install             # optional: run the gates on every commit
uv run pre-commit run --all-files     # full local gate
```

The gate runs ruff (lint + format), pyright (strict), interrogate (docstring
coverage), pytest with a coverage floor, and an `example/` smoke run. CI
(GitHub Actions) runs the same gates plus a 3-OS test matrix.

`example/example.py` contains worked examples: field customization, JSON
parsing and a recursive scanner built with the library combinators
(`recursive` / `sep_by`). `example/moe_calc.py` is a cute four-function
calculator built the same way -- its number field competes `int` and `float`
converter branches; run it for a demo, or add `--repl` to chat interactively.
`example/dice_catgirl.py` is its dice-rolling companion: it reads tabletop
notation (`3d6+2`), forecasts odds for a `?`-prefixed expression, and
comments on every cast -- demo mode, or `--repl` again.
`example/simple_kv.py` rounds the set off with a 40-line `key=value` config
parser: escaped-string and bare branches compete per field, with the metas
riding in PEP 695 `type` aliases.

## License

MIT. See [`LICENSE.md`](LICENSE.md).
