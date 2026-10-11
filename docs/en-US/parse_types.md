# Curated Types (parse_types)

## Overview

`infinity_parse.parse_types` ships ready-made converter types (`Annotated` aliases)
whose naming and semantics mirror the `parse` library's format specifiers (`{:d}`,
`{:%Y-%m-%d}`, …). They are ordinary type aliases — drop them into `scan[...]`
type arguments:

```python
from infinity_parse import scan
from infinity_parse import parse_types as t

scan[t.Int, t.SimpleDate]("{} {}")("42 2024-01-15")  # (42, date(2024, 1, 15))
```

---

## Character Classes

| Type | Input example | Result | parse spec | Notes |
| - | - | - | - | - |
| `t.Letters` | `abcXYZ` | `"abcXYZ"` | `{:l}` | ASCII letters only (`[a-zA-Z]+`) |
| `t.Word` | `a_1` | `"a_1"` | `{:w}` | Letters, digits, underscore (`\w+`) |
| `t.NonWord` | `!!` | `"!!"` | `{:W}` | Non-`\w` characters (`\W+`) |
| `t.Whitespace` | `"   "` | `"   "` | `{:s}` | Keeps raw whitespace (`strip=False`) |
| `t.NonWhitespace` | `x` | `"x"` | `{:S}` | Non-whitespace (`\S+`) |
| `t.NonDigit` | `x` | `"x"` | `{:D}` | Non-digits (`\D+`) |

> Two things to remember about `t.Whitespace`: the field keeps raw whitespace (no
> strip); and since `scan` strips the whole input first, whitespace-only input
> needs `scanall` / `search` (which do not strip the input).

```python
from infinity_parse import scanall
from infinity_parse import parse_types as t

scanall[t.Whitespace]("{}")("a  b")  # [("  ",)]
```

## Date-Times

| Type | Input example | Result | parse spec |
| - | - | - | - |
| `t.SimpleDate` | `2024-01-15` | `date(2024, 1, 15)` | `{:%Y-%m-%d}` |
| `t.SimpleTime` | `12:30` / `12:30:45` | `time(12, 30)` / `time(12, 30, 45)` | `{:%H:%M}` family |
| `t.IsoDateTime` | `2024-01-15T12:30:45+08:00` | `datetime` with tzinfo | `{:ti}` |
| `t.Rfc2822DateTime` | `Mon, 20 Jan 1972 10:21:36 +1000` | `datetime` with tzinfo | `{:te}` |
| `t.GlobalDate` | `20/1/1972 10:21:36 AM +1:00` | `datetime` | `{:tg}` |
| `t.UsDate` | `1/20/1972 10:21:36 PM +10:30` | `datetime` | `{:ta}` |
| `t.CtimeDateTime` | `Sun Sep 16 01:03:52 1973` | `datetime` | `{:tc}` |
| `t.HttpLogDateTime` | `21/Nov/2011:00:07:11 +0000` | `datetime` with tzinfo | `{:th}` |
| `t.SyslogDateTime` | `Nov 9 03:37:44` | `datetime` (current year filled in) | `{:ts}` |
| `t.AmPmTime` | `10:21:36 PM` / `10:21` | `time` (AM/PM and offset optional) | `{:tt}` |

- For `t.GlobalDate` / `t.UsDate` the date part is required; time, AM/PM and
  timezone offset are optional, and 12-hour clocks convert automatically (`PM`
  adds 12 hours).
- `t.IsoDateTime` accepts `T` or a space separator, optional seconds, a `Z` suffix
  and `+08:00` offsets.

## Numbers

| Type | Input example | Result | parse spec | Notes |
| - | - | - | - | - |
| `t.CommaInt` | `1,234,567` / `1.234.567` | `1234567` | `{:n}` | Thousands separators required |
| `t.Percent` | `12.5%` / `-.5%` | `0.125` / `-0.005` | `{:%}` | Percent to fraction |
| `t.HexInt` | `0x1F` / `FF` | `31` / `255` | `{:x}` | Prefix optional |
| `t.Int` | `42` / `-0x1F` / `0b101` / `-0o17` | `42` / `-31` / `5` / `-15` | `{:d}` | `0x` / `0b` / `0o` prefixes; `042` stays decimal |
| `t.Binary` | `0b101` / `101` | `5` | `{:b}` | Prefix optional |
| `t.Octal` | `0o17` / `17` | `15` | `{:o}` | Prefix optional |
| `t.Float` | `-1.5` / `.5` | `-1.5` | `{:f}` | Decimal point required (`1` and `1.` do not match) |
| `t.ExponentFloat` | `1.1e-10` / `NAN` / `INF` | `1.1e-10` | `{:e}` | Exponent required; special values case-insensitive |
| `t.GeneralFloat` | `42` / `1.5` / `4.2e1` | `42.0` | `{:g}` | Always returns `float` |
| `t.DecimalNumber` | `1.5` | `Decimal("1.5")` | `{:F}` | Decimal point required; returns `decimal.Decimal` |

## Building Types From Literals

Two generic builders turn a literal pattern / format string into a type.

### RegexString

`t.RegexString[Literal[pattern]]` resolves at runtime to
`Annotated[str, Converter(str, pattern=...)]`; type checkers see a `str` subtype
carrying the pattern, so plain `str` behavior is unaffected.

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import RegexString

type DashPair = RegexString[Literal[r"\d+-\d+"]]

scan[DashPair]("{}")("12-34")  # ('12-34',)
```

### DateTime

`t.DateTime[Literal[fmt]]` derives the capture pattern from a `strptime` format
string and parses with the same format string:

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import DateTime

type LogStamp = DateTime[Literal["%Y-%m-%d %H:%M:%S"]]

scan[LogStamp]("{}")("2024-01-15 12:30:45")
# (datetime(2024, 1, 15, 12, 30, 45),)
```

The shipped `t.CtimeDateTime` and `t.HttpLogDateTime` are exactly such aliases:
`DateTime[Literal["%a %b %d %H:%M:%S %Y"]]` and
`DateTime[Literal["%d/%b/%Y:%H:%M:%S %z"]]`.

Supported directives are a common subset: `a A b B d f H I j m M p S y Y z Z %`;
unsupported ones (e.g. `%Q`) raise `TypeError` at construction time.

## Examples

```python
from infinity_parse import scan
from infinity_parse import parse_types as t

# Mix built-in and curated types
scan[t.Int, t.Percent]("{} {}")("42 12.5%")  # (42, 0.125)

# Reuse the same curated type twice in one template
# (capture patterns contain no named groups, so nothing collides)
scan[t.SimpleDate, t.SimpleDate]("{} {}")(
    "2024-01-15 2025-02-03"
)  # (date(2024, 1, 15), date(2025, 2, 3))
```

## Notes

- `t.SyslogDateTime` stamps carry no year: the converter fills in the **current
  year** (following `parse`).
- `t.Whitespace` keeps raw spaces, but `scan` strips the whole input first —
  whitespace-only input needs `scanall` / `search`.
- `t.Float` and `t.DecimalNumber` require a decimal point; `t.CommaInt` requires
  thousands separators — this strictness matches the corresponding `parse`
  specifiers.
- Validation fails in two layers: pattern miss → `MatchError`; pattern matched but
  the value is invalid (e.g. `2024-13-45`) → `ConvertError`.
- Exact-match semantics follow the chosen `scan` / `search` / `scanall` mode (see
  [scanner.md](scanner.md)).
