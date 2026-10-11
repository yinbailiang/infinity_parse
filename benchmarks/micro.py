"""Micro-benchmarks for infinity_parse hot paths.

Run from the repository root:

    uv run python benchmarks/micro.py

Sections:

- ``construct``: building a fresh 60-field parser (``scan[metas](template)``),
  which exercises the cached per-field resolution;
- ``call``: a hot call on the reusable 60-field parser;
- ``blob``: capturing a 1 MB text with the default lazy ``.+?`` pattern versus
  the greedy DOTALL recipe from the docs.

Methodology: a warmup pass, then ``--repeat`` timed rounds with the garbage
collector disabled; each number is the best round normalized per call.
"""

import argparse
import gc
import time
from collections.abc import Callable
from typing import Annotated, Any, cast

from infinity_parse import Converter, scan


def timed(fn: Callable[[], object], inner: int, repeat: int) -> float:
    """Best round in microseconds per call."""
    for _ in range(max(1, inner // 10)):
        fn()
    best = float("inf")
    for _ in range(repeat):
        gc.disable()
        start = time.perf_counter()
        for _ in range(inner):
            fn()
        best = min(best, (time.perf_counter() - start) / inner)
        gc.enable()
    return best * 1e6


def main() -> None:
    """Run the micro-benchmarks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5, help="timed rounds")
    args = parser.parse_args()

    fields = 60
    template = " ".join(["{}"] * fields)
    metas = (int,) * fields
    number_line = " ".join(["1"] * fields)

    factory = cast(Any, scan)
    construct_us = timed(
        lambda: factory[metas](template), inner=200, repeat=args.repeat
    )

    reusable = factory[metas](template)
    call_us = timed(lambda: reusable(number_line), inner=2_000, repeat=args.repeat)
    if reusable(number_line) != (1,) * fields:
        raise SystemExit("60-field parser returned an unexpected result")

    blob = "x" * 1_000_000
    lazy = scan[str]("{}")
    greedy = scan[Annotated[str, Converter(str, pattern=r"(?s:.+)")]]("{}")
    if lazy(blob) != (blob,) or greedy(blob) != (blob,):
        raise SystemExit("blob capture returned an unexpected result")
    lazy_us = timed(lambda: lazy(blob), inner=5, repeat=args.repeat)
    greedy_us = timed(lambda: greedy(blob), inner=20_000, repeat=args.repeat)

    print(f"construct {fields} fields      : {construct_us:8.1f} us")
    print(f"call {fields} fields           : {call_us:8.1f} us")
    print(f"capture 1 MB  lazy .+?       : {lazy_us:8.1f} us")
    print(f"capture 1 MB  greedy (?s:.+) : {greedy_us:8.2f} us")


if __name__ == "__main__":
    main()
