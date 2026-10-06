"""dice_catgirl: a scanf-powered dice roller with a moe personality.

Rolls classic tabletop dice notation -- ``3d6+2``, ``1d20``, ``2d10-1`` --
and reacts to every cast, from critical hits to slippery cat paws::

    uv run python example/dice_catgirl.py
    uv run python example/dice_catgirl.py --repl

The three shapes (``NdM+K`` / ``NdM-K`` / ``NdM``) are three separate ``scan``
templates competing through an ordered ``alt`` choice, the bare ``NdM``
catch-all last; only ``MatchError`` -- the soft failure -- falls through.
In the REPL, ``?3d6+2`` forecasts the expected value and range instead of
rolling. Pass a seeded ``random.Random`` to :func:`roll` for reproducible
dice.
"""

import random
import sys
from dataclasses import dataclass

from infinity_parse import ScanError, alt, scan

MAX_DICE = 100


class DiceCatError(ValueError):
    """The dice spell could not be cast -- said cutely."""


@dataclass(frozen=True)
class Dice:
    """A parsed dice pool: ``count`` dice of ``faces`` sides, plus ``modifier``."""

    count: int
    faces: int
    modifier: int = 0


@dataclass(frozen=True)
class Roll:
    """One cast: the ``dice`` pool and every die's ``results``."""

    dice: Dice
    results: tuple[int, ...]

    @property
    def total(self) -> int:
        """Sum of all dice plus the modifier."""
        return sum(self.results) + self.dice.modifier

    @property
    def expression(self) -> str:
        """Canonical spelling of the pool, e.g. ``3d6+2``."""
        sign = f"{self.dice.modifier:+d}" if self.dice.modifier else ""
        return f"{self.dice.count}d{self.dice.faces}{sign}"


_plus = scan[int, int, int]("{}d{}+{}")
_minus = scan[int, int, int]("{}d{}-{}")
_plain = scan[int, int]("{}d{}")


def _plus_dice(text: str) -> Dice:
    count, faces, modifier = _plus(text)
    return Dice(count=count, faces=faces, modifier=modifier)


def _minus_dice(text: str) -> Dice:
    count, faces, modifier = _minus(text)
    return Dice(count=count, faces=faces, modifier=-modifier)


def _plain_dice(text: str) -> Dice:
    count, faces = _plain(text)
    return Dice(count=count, faces=faces)


# Order matters: the bare ``NdM`` catch-all must come last.
_read_dice = alt(_plus_dice, _minus_dice, _plain_dice)


def parse(expression: str) -> Dice:
    """Parse ``NdM``, ``NdM+K`` or ``NdM-K`` and validate the pool."""
    try:
        dice = _read_dice(expression)
    except ScanError as error:
        raise DiceCatError(
            f"喵呜... 这不是骰子咒语啦: {expression!r} (试试 '3d6+2') (>_<)"
        ) from error
    if not 1 <= dice.count <= MAX_DICE:
        raise DiceCatError(f"骰子数量要在 1 到 {MAX_DICE} 之间啦: {expression!r}")
    if dice.faces < 2:
        raise DiceCatError(f"骰子至少要有 2 面喔: {expression!r}")
    return dice


def roll(expression: str, rng: random.Random | None = None) -> Roll:
    """Cast the dice; pass a seeded ``rng`` to make the results reproducible."""
    dice = parse(expression)
    source = rng if rng is not None else random.Random()
    results = tuple(source.randint(1, dice.faces) for _ in range(dice.count))
    return Roll(dice=dice, results=results)


def forecast(expression: str) -> str:
    """Expected value and range of one expression, without rolling."""
    dice = parse(expression)
    average = dice.count * (dice.faces + 1) / 2 + dice.modifier
    lowest = dice.count + dice.modifier
    highest = dice.count * dice.faces + dice.modifier
    return f"{expression.strip()}: 期望 {average:g}, 范围 {lowest} ~ {highest}"


def describe(roll: Roll) -> str:
    """Format one roll as ``3d6+2: [3, 5, 1] = 9 +2 -> 11``."""
    faces = ", ".join(str(die) for die in roll.results)
    subtotal = sum(roll.results)
    modifier = f" {roll.dice.modifier:+d}" if roll.dice.modifier else ""
    return f"{roll.expression}: [{faces}] = {subtotal}{modifier} -> {roll.total}"


def react(roll: Roll) -> str:
    """Catgirl commentary for one roll."""
    dice, results = roll.dice, roll.results
    if dice.count == 1 and dice.faces == 20 and results[0] == 20:
        return "大成功喵!! 命运站在猫爪这边! (=^_^=)"
    if dice.count == 1 and dice.faces == 20 and results[0] == 1:
        return "啊呜... 大失败, 猫猫耳朵垂下来了 (T_T)"
    if len(results) > 1 and all(die == dice.faces for die in results):
        return "全...全部满点!? 猫神附体啦!! (=^_^=)"
    if len(results) > 1 and all(die == 1 for die in results):
        return "呜哇... 一个都没站住, 猫爪打滑了 (>_<)"
    average = dice.count * (dice.faces + 1) / 2
    subtotal = sum(results)
    if subtotal >= average * 1.5:
        return "手气超棒喵! 今天适合出门冒险~"
    if subtotal <= average * 0.5:
        return "呜... 下次一定喵 (._.)"
    return "普普通通, 稳稳的喵~"


def _repl() -> None:
    """Chat with the dice catgirl until EOF or a quit word."""
    print("dice_catgirl 已就位! 输入 3d6+2 掷骰, ?3d6+2 看期望, 输入 q 退出 (=^_^=)")
    while True:
        try:
            line = input("dice> ")
        except EOFError:
            print()
            break
        spell = line.strip()
        if spell.casefold() in {"q", "quit", "exit"}:
            print("呼噜呼噜~ 想再玩随时叫我喵!")
            break
        if not spell:
            continue
        try:
            if spell.startswith("?"):
                print(f"  {forecast(spell[1:])}")
            else:
                result = roll(spell)
                print(f"  {describe(result)}   {react(result)}")
        except DiceCatError as error:
            print(f"  {error}")


def _demo() -> None:
    """Cast a few fixed spells, then two cute failures."""
    print("dice_catgirl 值班中! (=^_^=)")
    for spell in ("1d20", "3d6+2", "2d10-1", "4d6"):
        result = roll(spell)
        print(f"喵! {describe(result)}   {react(result)}")
    print(f"? {forecast('3d6+2')}")
    for broken in ("d6", "3d1"):
        try:
            roll(broken)
        except DiceCatError as error:
            print(f"呜... {error}")


if __name__ == "__main__":
    if "--repl" in sys.argv[1:]:
        _repl()
    else:
        _demo()
