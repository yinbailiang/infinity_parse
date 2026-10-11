# Scanner — Entry Points & Field Declarations

## Overview

The `scanner` module is the front door of InfinityParse: it binds a template and
converter types into a reusable parser and offers three matching modes. The type
arguments also decide how fields convert — each type argument resolves into one or
more converter branches that compete in declaration order.

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
```

---

## Entry Points

| Entry | Call shape | Semantics | Returns |
| - | - | - | - |
| `scan[Meta]` | `scan[int]("{}")("42")` | Full match (strips the input first) | `tuple[*Meta]` |
| `search[Meta]` | `search[int]("{}")("a 42 b")` | First match anywhere | `tuple[*Meta] \| None` |
| `scanall[Meta]` | `scanall[int]("{}")("1 2 3")` | All non-overlapping matches, left to right | `list[tuple[*Meta]]` |
| `Scanner[Meta]` | `Scanner[int]("{}")` | The same three, exposed as instance methods | `Scanner` instance |

`Scanner` instance methods map one-to-one to the entry points:

| Method | Equivalent entry | Notes |
| - | - | - |
| `fullmatch(input_value)` | `scan[...]` | The template must cover the whole (stripped) input, else `MatchError` |
| `search(input_value)` | `search[...]` | Returns `None` when there is no match |
| `findall(input_value)` | `scanall[...]` | Returns an empty list when there is no match |

### Signatures

```python
class Scanner[*Meta]:
    def fullmatch(self, input_value: str) -> tuple[*Meta]
    def search(self, input_value: str) -> tuple[*Meta] | None
    def findall(self, input_value: str) -> list[tuple[*Meta]]

class scan[*Meta](Scanner[*Meta]):
    def __call__(self, input_value: str) -> tuple[*Meta]

class search[*Meta](Scanner[*Meta]):
    def __call__(self, input_value: str) -> tuple[*Meta] | None

class scanall[*Meta](Scanner[*Meta]):
    def __call__(self, input_value: str) -> list[tuple[*Meta]]
```

> `scan[int]` returns a real generic alias (a `types.GenericAlias` subclass):
> `get_origin(scan[int]) is scan` and `get_args(scan[int]) == (int,)`; calling the
> alias with `(template)` builds the parser. Subscriptions keep separate state, so
> parsers can be reused freely.

### How the Three Modes Differ

```python
from typing import Annotated

from infinity_parse import Converter, scan, scanall, search

Number = Annotated[int, Converter(int, pattern=r"\d+")]

scan[Number]("{}")("42")  # (42,)
search[Number]("{}")("answer 42")  # (42,) — first match
scanall[Number]("{}")("1 2 3")  # [(1,), (2,), (3,)] — every match
search[Number]("{}")("nothing")  # None
```

- `scan` strips the whole input first, then requires the template to cover all of it.
- `search` / `scanall` scan the raw input (no outer strip).
- In all three modes a converter failure aborts with `ConvertError` — `search` /
  `scanall` never skip a failing match to try a later one.

---

## Template Syntax

A template consists of literal text and `{}` placeholders:

| Spelling | Meaning |
| - | - |
| `{}` | One field; default capture pattern `.+?` (non-empty, single-line, lazy) |
| `{{` / `}}` | Literal braces `{` / `}` |
| Whitespace run | Matches any whitespace run (`\s+`), newlines included |
| A single `{` or `}` | `ValueError` at construction time |

```python
scan[int]("{{}}={}")("{}= 42")  # (42,)
scan[int]("{{{}}}")("{42}")  # (42,)
scan[int]("{ x }")  # ValueError: single '{' in template ...
```

- Whitespace around the input (and around each captured field) is ignored by
  default; a `Converter(strip=False)` keeps it (see [engine.md](engine.md)).
- Template whitespace is lenient: `"x={}, y={}"` matches `"x= 1,   y=2"`.
- The default field pattern never matches a newline; when the input contains one,
  let the whitespace between adjacent fields absorb it (e.g. `"1\nhello"` matches
  `"{} {}"`).

---

## Declaring Fields

Each type argument resolves as follows: if the annotation carries a `Converter`
spec, that spec is used; otherwise it falls back to a "default branch" — a built-in
converter when the type is in the built-in table, or the type itself called as the
converter.

### Built-in Defaults

| Declaration | Conversion | Example |
| - | - | - |
| `bool` | `true` / `false` / `1` / `0` (case-insensitive) | `scan[bool]("{}")("true")` → `(True,)` |
| `dict` / `list` / `tuple` / `set` / `frozenset` (generic forms included) | `ast.literal_eval` (Python literal syntax) | `scan[list[int]]("{}")("[1, 2, 3]")` → `([1, 2, 3],)` |
| Any other callable type | Called directly: `int` / `float` / `str`, … | `scan[int]("{}")("42")` → `(42,)` |
| Custom classes | The class is called as the converter | `scan[Hex]("{}")("ff")` → `Hex("ff")` |

```python
from infinity_parse import scan

scan[dict[str, str]]("{}")('{"key": "value"}')  # ({"key": "value"},)
scan[tuple[int, str]]("{}")("(1, 'a')")  # ((1, "a"),)
```

Containers parse as Python literals — `{'a': 0x10}` works too (hex follows Python
syntax).

### Annotated[T, Converter(...)]

Attach a converter spec to a field with `typing.Annotated`: custom capture pattern,
label, `strip` flag and `re` flags (parameters in [engine.md](engine.md)).

```python
from typing import Annotated

from infinity_parse import Converter, scan

parse = scan[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
]("age={} name={}")

parse('age=42 name="kim"')  # (42, '"kim"')
```

Rules:

- The spec replaces the default branch; other `Annotated` metadata (e.g. doc
  strings) is ignored.
- Nested `Annotated` wrappers flatten into one layer:
  `Annotated[Annotated[int, C], "doc"]` is equivalent to `Annotated[int, C]`.
- PEP 695 `type` aliases expand at runtime exactly as type checkers expand them
  (alias chains included; plain aliases like `type MyInt = int` pass through).

```python
type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,)
```

### OneOf — Competing Branches

A field may pack several branches: `Annotated[T, OneOf[C1, C2]]`. Branches are
tried in declaration order; the first one whose **pattern** matches takes effect —
if its converter then fails, the whole scan aborts with `ConvertError` and
**never falls back to a later branch**.

```python
from typing import Annotated

from infinity_parse import Converter, OneOf, scan

parse_number = scan[
    Annotated[
        int | float,
        OneOf[
            Converter(int, pattern=r"\d+"),
            Converter(float, pattern=r"\d+\.\d+"),
        ],
    ]
]("{}")

parse_number("42")  # (42,)
parse_number("3.14")  # (3.14,)
```

| Rule | Behavior |
| - | - |
| Branch competition | The first branch whose pattern matches wins (even if later branches could match too) |
| Conversion failure | Hard failure: abort with `ConvertError`, no fallback |
| `OneOf[non-Converter]` | `TypeError` at construction time |
| `OneOf[()]` (empty) | `TypeError` at construction time |
| Calling `OneOf()` directly | `TypeError` (subscription syntax required) |

### Union Sugar

A `|` union of `Annotated` members is sugar for the same competition: it expands
into branch groups in member order; a member without a spec contributes its default
branch.

```python
parse_number = scan[
    Annotated[int, Converter(int, pattern=r"\d+")]
    | Annotated[float, Converter(float, pattern=r"\d+\.\d+")]
]("{}")

parse_number("42")  # (42,)
parse_number("3.14")  # (3.14,)
```

- A member carrying its own `OneOf` competes as a group, in member order.
- A spec on an `Annotated` wrapping the whole union binds it as one branch group;
  combining that with member specs raises `ValueError` at construction time
  (ambiguous).
- Alias members of a union (e.g. `type Digits = ...`) expand as well.

```python
# Spec binds the whole union: legal
scan[Annotated[int | str, Converter(int, pattern=r"\d+")]]("{}")("42")  # (42,)

# Outer spec + member spec: ValueError
scan[
    Annotated[
        Annotated[int, Converter(int, pattern=r"\d+")] | str,
        Converter(str, name="outer"),
    ]
]("{}")
```

### The One-Layer Rule

**All branches of a field must sit on one `Annotated` layer, packed in a single
`OneOf`.** An outer layer cannot override an inner one, and specs hidden deep
inside aliases would be ambiguous — so mixing specs across layers is rejected at
construction time:

```python
type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,) — legal

scan[Annotated[Age, Converter(int, name="outer")]]("{}")
# ValueError: multiple Converter specs on one field; pack competing branches
#   in OneOf[*Converter], e.g. Annotated[T, OneOf[C1, C2]]
```

Bare multiple `Converter` specs on the same layer (not packed in `OneOf`) are
rejected the same way:

```python
scan[
    Annotated[
        str,
        Converter(str, pattern=r"\d+"),
        Converter(str, pattern=r"[a-z]+"),  # ValueError
    ]
]("{}")
```

### Low-Level Resolution

To resolve annotations by hand, use `resolve_field(declared, convs)` — it turns a
"declared type + converter list" into a `Field` (pair it with `Template` to build
low-level parsers; see [engine.md](engine.md)):

```python
from infinity_parse import Converter, resolve_field

field = resolve_field(dict, [Converter(lambda raw: raw, name="raw")])
field.converters[0].fn  # <lambda>
```

---

## Typed Results

The result tuple's type mirrors the type arguments one-to-one; pyright infers them
directly:

```python
import json
from typing import Annotated, assert_type

from infinity_parse import Converter, scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
assert_type(a, int)  # pyright check passes
assert_type(b, float)
assert_type(scan[int, int]("{} {}")("7 8"), tuple[int, int])
assert_type(
    scan[Annotated[dict[str, str], Converter(json.loads)]]("{}")('{"k": "v"}'),
    tuple[dict[str, str]],
)
```

## Reusable Parsers

Build once, call many times; subscriptions are independent:

```python
parse_pair = scan[int, int]("{} {}")
parse_pair("7 8")  # (7, 8)
parse_pair("9 10")  # (9, 10)
```

## Notes

- `scan[...]` requires at least one converter type: calling `scan(...)` directly or
  subscribing with nothing raises `TypeError`; for zero-field templates use
  `Template` directly (see [engine.md](engine.md)).
- The number of `{}` placeholders must match the number of type arguments, else
  construction raises `ValueError` (e.g. `scan[int]("hello")`).
- Converters must be callable and hashable (they participate in the compile cache).
- `MatchError` means "did not match"; `ConvertError` means "matched but failed to
  convert" — the two are not interchangeable (see [engine.md](engine.md)).
