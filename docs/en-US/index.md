# InfinityParse

**Type-safe, `scanf`-style string parsing for Python.**

InfinityParse maps each `{}` placeholder to one converter type: in
`scan[int, float]("{} {}")` the type arguments declare how fields are converted;
call the parser with an input string and get a strongly-typed tuple back.
Zero runtime dependencies, Python 3.14+ (PEP 695 generics).

## Installation

```bash
# uv (recommended)
uv add infinity_parse

# or pip
pip install infinity_parse
```

## Quick Links

- [Core Overview](infinity_parse.md) — scan flow and component map
- [Scanner](scanner.md) — the three matching modes, template syntax and field declarations
- [Engine](engine.md) — `Converter` per-field configuration, `Template` compilation and the error model
- [Curated Types (parse_types)](parse_types.md) — date-time / number / character-class converters out of the box
- [Combinators](combinators.md) — build larger parsers from scanners
- [README (Quick Start)](https://github.com/yinbailiang/infinity_parse/blob/main/README.md)

## Minimal Example

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
# a=1 (int), b=2.5 (float), c="hello" (str)
```
