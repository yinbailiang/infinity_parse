"""Tests for the curated ``parse``-style types."""

import math
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, assert_type, cast

import pytest

from infinity_parse import ConvertError, MatchError, scan, scanall
from infinity_parse import parse_types as t

CASES: list[tuple[str, Any, str, Any]] = [
    ("letters", t.Letters, "abcXYZ", "abcXYZ"),
    ("word", t.Word, "a_1", "a_1"),
    ("non-word", t.NonWord, "!!", "!!"),
    ("non-whitespace", t.NonWhitespace, "x", "x"),
    ("non-digit", t.NonDigit, "x", "x"),
    ("simple-date", t.SimpleDate, "2024-01-15", date(2024, 1, 15)),
    ("simple-time", t.SimpleTime, "12:30:45", time(12, 30, 45)),
    ("simple-time-minute", t.SimpleTime, "12:30", time(12, 30)),
    (
        "iso-datetime",
        t.IsoDateTime,
        "2024-01-15T12:30:45+08:00",
        datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone(timedelta(hours=8))),
    ),
    (
        "iso-datetime-z",
        t.IsoDateTime,
        "2024-01-15 12:30Z",
        datetime(2024, 1, 15, 12, 30, tzinfo=UTC),
    ),
    (
        "rfc2822",
        t.Rfc2822DateTime,
        "Mon, 20 Jan 1972 10:21:36 +1000",
        datetime(1972, 1, 20, 10, 21, 36, tzinfo=timezone(timedelta(hours=10))),
    ),
    (
        "global-date",
        t.GlobalDate,
        "20/1/1972 10:21:36 AM +1:00",
        datetime(1972, 1, 20, 10, 21, 36, tzinfo=timezone(timedelta(hours=1))),
    ),
    ("global-date-bare", t.GlobalDate, "20/1/1972", datetime(1972, 1, 20)),
    (
        "us-date",
        t.UsDate,
        "1/20/1972 10:21:36 PM +10:30",
        datetime(
            1972, 1, 20, 22, 21, 36, tzinfo=timezone(timedelta(hours=10, minutes=30))
        ),
    ),
    (
        "ctime",
        t.CtimeDateTime,
        "Sun Sep 16 01:03:52 1973",
        datetime(1973, 9, 16, 1, 3, 52),
    ),
    (
        "http-log",
        t.HttpLogDateTime,
        "21/Nov/2011:00:07:11 +0000",
        datetime(2011, 11, 21, 0, 7, 11, tzinfo=UTC),
    ),
    (
        "syslog",
        t.SyslogDateTime,
        "Nov 9 03:37:44",
        datetime(datetime.now().year, 11, 9, 3, 37, 44),
    ),
    (
        "ampm-time",
        t.AmPmTime,
        "10:21:36 PM -5:30",
        time(22, 21, 36, tzinfo=timezone(timedelta(hours=-5, minutes=-30))),
    ),
    ("ampm-time-plain", t.AmPmTime, "10:21", time(10, 21)),
    ("comma-int", t.CommaInt, "1,234,567", 1234567),
    ("comma-int-eu", t.CommaInt, "1.234.567", 1234567),
    ("comma-int-signed", t.CommaInt, "-1,234", -1234),
    ("percent", t.Percent, "12.5%", 0.125),
    ("percent-small", t.Percent, "-.5%", -0.005),
    ("hex-int", t.HexInt, "0x1F", 31),
    ("hex-int-bare", t.HexInt, "FF", 255),
    ("int-hex", t.Int, "-0x1F", -31),
    ("int-bin", t.Int, "0b101", 5),
    ("int-oct", t.Int, "-0o17", -15),
    ("int-decimal", t.Int, "+042", 42),
    ("binary", t.Binary, "101", 5),
    ("binary-prefixed", t.Binary, "0b101", 5),
    ("octal", t.Octal, "17", 15),
    ("octal-prefixed", t.Octal, "0o17", 15),
    ("float", t.Float, "-1.5", -1.5),
    ("exponent-float", t.ExponentFloat, "1.1e-10", 1.1e-10),
    ("general-float", t.GeneralFloat, "4.2e1", 42.0),
    ("general-float-int", t.GeneralFloat, "42", 42.0),
    ("decimal", t.DecimalNumber, "1.5", Decimal("1.5")),
]


@pytest.mark.parametrize(
    ("alias", "text", "expected"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_curated_type_parses(alias: Any, text: str, expected: Any) -> None:
    assert cast(Any, scan)[alias]("{}")(text) == (expected,)


def test_exponent_float_special_values() -> None:
    (value,) = scan[t.ExponentFloat]("{}")("NAN")
    assert math.isnan(value)
    assert scan[t.ExponentFloat]("{}")("INF") == (float("inf"),)


def test_whitespace_keeps_raw_spaces() -> None:
    assert scan[t.Whitespace]("x{}y")("x   y") == ("   ",)
    assert scanall[t.Whitespace]("{}")("a  b") == [("  ",)]


def test_whitespace_only_input_needs_a_scan_mode() -> None:
    # ``scan`` strips the whole input first, so whitespace-only input cannot
    # full-match; ``scanall`` / ``search`` see the raw input.
    with pytest.raises(MatchError):
        scan[t.Whitespace]("{}")("   ")


def test_repeated_fields_share_one_template() -> None:
    assert scan[t.SimpleDate, t.SimpleDate]("{} {}")("2024-01-15 2025-02-03") == (
        date(2024, 1, 15),
        date(2025, 2, 3),
    )
    assert scan[t.GlobalDate, t.GlobalDate]("{} | {}")("20/1/1972 | 2/3/2001") == (
        datetime(1972, 1, 20),
        datetime(2001, 3, 2),
    )


def test_invalid_values_raise_scan_error() -> None:
    with pytest.raises(ConvertError):
        scan[t.SimpleDate]("{}")("2024-13-45")
    with pytest.raises(MatchError):
        scan[t.Percent]("{}")("12")
    with pytest.raises(MatchError):
        scan[t.Int]("{}")("abc")


def test_result_types_are_inferred() -> None:
    assert_type(scan[t.Int]("{}")("42"), tuple[int])
    assert_type(scan[t.Int, t.Percent]("{} {}")("1 12.5%"), tuple[int, float])
    assert_type(scan[t.SimpleDate]("{}")("2024-01-15"), tuple[date])
    assert_type(scan[t.AmPmTime]("{}")("10:21 PM"), tuple[time])
