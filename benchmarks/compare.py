"""Three-library benchmark: infinity_parse vs parse vs temparse.

Run from the repository root:

    uv run --extra benchmark python benchmarks/compare.py

Each library parses the same log line with its compiled, reusable parser.
Every parser is verified against the others before timing starts; each run is
preceded by a warmup, and timed rounds disable the garbage collector. The table
reports the best and median round out of ``--repeat`` rounds, and the versions
of all three libraries are printed so numbers can be attributed.

The matching-only lower bound is measured for both implementations as well:
infinity_parse via ``Scanner.raw_pattern`` (the compiled regex) and ``parse``
via ``evaluate_result=False`` (a raw ``Match``); neither converts fields.
"""

import argparse
import datetime
import gc
import platform
import re
import sys
import time
from collections.abc import Callable
from functools import partial
from importlib.metadata import version

from infinity_parse import parse_types as t
from infinity_parse import scan

LINE = "2024-03-15 12:30:45 GET /api/items 200 1234 5678 0.123"
TEMPLATE = "{} {} {} {} {} {} {} {}"

Parser = Callable[[str], object]


def build_parsers() -> list[tuple[str, Parser]]:
    """Build one compiled, reusable parser per library for ``LINE``."""
    try:
        import parse as parse_lib
        from temparse import Parser as TemParser
    except ImportError:
        sys.exit(
            "this benchmark needs the 'benchmark' extra: run with "
            "`uv run --extra benchmark python benchmarks/compare.py`"
        )
    infinity = scan[
        t.SimpleDate,
        t.SimpleTime,
        t.Letters,
        t.NonWhitespace,
        t.Int,
        t.Int,
        t.Int,
        t.Float,
    ](TEMPLATE)
    parse_compiled = parse_lib.compile(
        "{:%Y-%m-%d} {:%H:%M:%S} {:l} {} {:d} {:d} {:d} {:f}"
    )
    temparse_compiled = TemParser[
        datetime.date,
        datetime.time,
        str,
        str,
        int,
        int,
        int,
        float,
    ](
        t"{datetime.date:%Y-%m-%d} {datetime.time:%H:%M:%S} "
        t"{str} {str} {int} {int} {int} {float}"
    )
    infinity_pattern = infinity.raw_pattern
    return [
        ("infinity_parse", infinity),
        (
            "infinity_parse (match only)",
            lambda line: infinity_pattern.fullmatch(line.strip()),
        ),
        ("temparse", temparse_compiled.parse),
        ("parse", parse_compiled.parse),
        (
            "parse (match only)",
            partial(parse_compiled.parse, evaluate_result=False),
        ),
    ]


def verify(parsers: list[tuple[str, Parser]]) -> None:
    """All libraries must produce the same values before timing starts."""
    expected = tuple(parsers[0][1](LINE))
    for label, parse_row in parsers[1:]:
        value = parse_row(LINE)
        if value is None:
            raise SystemExit(f"{label}: no match on the workload line")
        evaluator = getattr(value, "evaluate_result", None)
        if callable(evaluator):
            # parse's lean mode returns a lazy Match; evaluate it for checking.
            value = evaluator()
        if isinstance(value, re.Match):
            if value.group(0) != LINE:
                raise SystemExit(f"{label}: full match does not cover the line")
            continue  # match-only entries produce no values
        fixed = getattr(value, "fixed", value)
        if tuple(fixed) != expected:
            raise SystemExit(f"{label}: unexpected result {value!r} != {expected!r}")


def bench(parse_row: Parser, rows: int, repeat: int) -> list[float]:
    """Timed rounds in seconds, sorted best first."""
    for _ in range(2_000):
        parse_row(LINE)
    rounds: list[float] = []
    for _ in range(repeat):
        gc.disable()
        start = time.perf_counter()
        for _ in range(rows):
            parse_row(LINE)
        rounds.append(time.perf_counter() - start)
        gc.enable()
    return sorted(rounds)


def main() -> None:
    """Run the comparison and print the result table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000, help="rows to parse")
    parser.add_argument("--repeat", type=int, default=3, help="timed rounds")
    args = parser.parse_args()

    parsers = build_parsers()
    verify(parsers)

    print(f"CPython {platform.python_version()} on {platform.system()}")
    for name in ("infinity-parse", "parse", "temparse"):
        print(f"  {name} {version(name)}")
    print(f"workload: {LINE!r}")
    print(f"rows: {args.rows}  rounds: {args.repeat} (best/median shown)\n")

    best: dict[str, float] = {}
    width = max(len(label) for label, _ in parsers) + 1
    for label, parse_row in parsers:
        rounds = bench(parse_row, args.rows, args.repeat)
        top = rounds[0]
        median = rounds[len(rounds) // 2]
        best[label] = top
        print(
            f"{label:<{width}} best {top * 1000:7.1f} ms  "
            f"median {median * 1000:7.1f} ms  "
            f"{args.rows / top / 1000:6.1f}k rows/s  "
            f"{top / args.rows * 1e6:5.2f} us/row"
        )
    base = best["infinity_parse"]
    for label in ("temparse", "parse"):
        print(
            f"speedup: infinity_parse is {best[label] / base:.1f}x faster than {label}"
        )
    match_only = best["infinity_parse (match only)"]
    parse_only = best["parse (match only)"]
    print(
        f"match-only: infinity_parse {match_only / args.rows * 1e6:.2f} us/row  "
        f"vs parse {parse_only / args.rows * 1e6:.2f} us/row"
    )


if __name__ == "__main__":
    main()
