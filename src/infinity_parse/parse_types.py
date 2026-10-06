"""Curated ``parse``-style converter types (``std::scan`` specifiers)."""

import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Annotated

from .engine import Converter

__all__: list[str] = [
    "AmPmTime",
    "Binary",
    "CommaInt",
    "CtimeDateTime",
    "DecimalNumber",
    "ExponentFloat",
    "Float",
    "GeneralFloat",
    "GlobalDate",
    "HexInt",
    "HttpLogDateTime",
    "Int",
    "IsoDateTime",
    "Letters",
    "NonDigit",
    "NonWhitespace",
    "NonWord",
    "Octal",
    "Percent",
    "Rfc2822DateTime",
    "SimpleDate",
    "SimpleTime",
    "SyslogDateTime",
    "UsDate",
    "Whitespace",
    "Word",
]

# --------------------------------------------- 字符组(parse 的 l/w/W/s/S/D)

type Letters = Annotated[str, Converter(str, pattern=r"[a-zA-Z]+", name="Letters")]
# 纯 ASCII 字母;对应 parse 的 {:l}。


type Word = Annotated[str, Converter(str, pattern=r"\w+", name="Word")]
# 字母、数字、下划线;对应 parse 的 {:w}。


type NonWord = Annotated[str, Converter(str, pattern=r"\W+", name="NonWord")]
# 非 \w 字符;对应 parse 的 {:W}。


type Whitespace = Annotated[
    str,
    Converter(str, pattern=r"\s+", strip=False, name="Whitespace"),
]
# 空白串(保留原样,不做 strip);对应 parse 的 {:s}。


type NonWhitespace = Annotated[
    str,
    Converter(str, pattern=r"\S+", name="NonWhitespace"),
]
# 非空白;对应 parse 的 {:S}。


type NonDigit = Annotated[str, Converter(str, pattern=r"\D+", name="NonDigit")]
# 非数字;对应 parse 的 {:D}。

# ---------------------------------------------------------------- 日期与时间


def _parse_simple_date(text: str) -> date:
    """``YYYY-MM-DD`` -> ``datetime.date``。"""
    return date.fromisoformat(text)


type SimpleDate = Annotated[
    date,
    Converter(_parse_simple_date, pattern=r"\d{4}-\d{2}-\d{2}", name="SimpleDate"),
]
# 2024-01-15 -> datetime.date;对应 parse 的 {:%Y-%m-%d}。


def _parse_simple_time(text: str) -> time:
    """``HH:MM`` / ``HH:MM:SS`` -> ``datetime.time``。"""
    return time.fromisoformat(text)


type SimpleTime = Annotated[
    time,
    Converter(
        _parse_simple_time,
        pattern=r"\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?",
        name="SimpleTime",
    ),
]
# 12:30 / 12:30:45 -> datetime.time;对应 parse 的 {:%H:%M} 一族。


def _parse_iso_datetime(text: str) -> datetime:
    """ISO 8601 日期时间(含 ``Z`` / 时区偏移)-> ``datetime.datetime``。"""
    return datetime.fromisoformat(text)


type IsoDateTime = Annotated[
    datetime,
    Converter(
        _parse_iso_datetime,
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?",
        name="IsoDateTime",
    ),
]
# 2024-01-15T12:30:45+08:00(空格分隔 / 省略秒 / 带 Z 均可);对应 parse 的 {:ti}。


def _timezone_from(sign: str, hours: str, minutes: str) -> timezone:
    """把 ``+1:00`` 形式的时区文本转成 ``timezone`` 偏移。"""
    offset = timedelta(hours=int(hours), minutes=int(minutes))
    return timezone(-offset if sign == "-" else offset)


def _parse_rfc2822_datetime(text: str) -> datetime:
    """RFC 2822 邮件日期时间 -> 带时区的 ``datetime``。"""
    return parsedate_to_datetime(text)


_RFC2822_PATTERN = (
    r"[A-Za-z]{3},\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+[+-]\d{4}"
)

type Rfc2822DateTime = Annotated[
    datetime,
    Converter(
        _parse_rfc2822_datetime, pattern=_RFC2822_PATTERN, name="Rfc2822DateTime"
    ),
]
# Mon, 20 Jan 1972 10:21:36 +1000;对应 parse 的 {:te}。

# 日/月与月/日两个日期正则共享的尾部:时间与 AM/PM 可选,时区偏移可选。
_DATE_TAIL = (
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
    r"(?:\s*(?P<ampm>[AaPp][Mm]))?)?"
    r"(?:\s*(?P<tzsign>[+-])(?P<tzhour>\d{1,2}):?(?P<tzminute>\d{2}))?"
)

_GLOBAL_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})" + _DATE_TAIL
)
_US_DATE_RE = re.compile(
    r"(?P<month>\d{1,2})[/-](?P<day>\d{1,2})[/-](?P<year>\d{4})" + _DATE_TAIL
)


def _build_date_match(match: re.Match[str]) -> datetime:
    """把上面两个日期正则的命名组装成 ``datetime``。"""
    hour = int(match["hour"] or 0)
    if match["ampm"] is not None:
        hour %= 12
        if match["ampm"].upper() == "PM":
            hour += 12
    tzinfo = None
    if match["tzsign"] is not None:
        tzinfo = _timezone_from(match["tzsign"], match["tzhour"], match["tzminute"])
    return datetime(
        int(match["year"]),
        int(match["month"]),
        int(match["day"]),
        hour,
        int(match["minute"] or 0),
        int(match["second"] or 0),
        tzinfo=tzinfo,
    )


def _parse_global_date(text: str) -> datetime:
    """日/月顺序的日期时间(见 ``GlobalDate``)。"""
    match = _GLOBAL_DATE_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"cannot parse {text!r} as a global date")
    return _build_date_match(match)


def _parse_us_date(text: str) -> datetime:
    """月/日顺序的日期时间(见 ``UsDate``)。"""
    match = _US_DATE_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"cannot parse {text!r} as a US date")
    return _build_date_match(match)


# 捕获模式不带命名组,避免同一模板里多次使用时组名冲突。
_GLOBAL_DATE_PATTERN = (
    r"\d{1,2}[/-]\d{1,2}[/-]\d{4}"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)?"
    r"(?:\s*[+-]\d{1,2}:?\d{2})?"
)


type GlobalDate = Annotated[
    datetime,
    Converter(_parse_global_date, pattern=_GLOBAL_DATE_PATTERN, name="GlobalDate"),
]
# 20/1/1972 10:21:36 AM +1:00(日/月,时间与时区可选);对应 parse 的 {:tg}。


type UsDate = Annotated[
    datetime,
    Converter(_parse_us_date, pattern=_GLOBAL_DATE_PATTERN, name="UsDate"),
]
# 1/20/1972 10:21:36 PM +10:30(月/日);对应 parse 的 {:ta}。


def _parse_ctime_datetime(text: str) -> datetime:
    """``ctime`` 风格日期时间。"""
    return datetime.strptime(text, "%a %b %d %H:%M:%S %Y")


type CtimeDateTime = Annotated[
    datetime,
    Converter(
        _parse_ctime_datetime,
        pattern=r"[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}",
        name="CtimeDateTime",
    ),
]
# Sun Sep 16 01:03:52 1973;对应 parse 的 {:tc}。


def _parse_http_log_datetime(text: str) -> datetime:
    """HTTP 日志风格日期时间(带 ``+0000`` 偏移)。"""
    return datetime.strptime(text, "%d/%b/%Y:%H:%M:%S %z")


type HttpLogDateTime = Annotated[
    datetime,
    Converter(
        _parse_http_log_datetime,
        pattern=r"\d{1,2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}\s+[+-]\d{4}",
        name="HttpLogDateTime",
    ),
]
# 21/Nov/2011:00:07:11 +0000;对应 parse 的 {:th}。


def _parse_syslog_datetime(text: str) -> datetime:
    """Linux 系统日志日期时间(缺年份,按 parse 约定取当前年)。"""
    return datetime.strptime(f"{datetime.now().year} {text}", "%Y %b %d %H:%M:%S")


type SyslogDateTime = Annotated[
    datetime,
    Converter(
        _parse_syslog_datetime,
        pattern=r"[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
        name="SyslogDateTime",
    ),
]
# Nov 9 03:37:44(年份为当前年,与 parse 一致);对应 parse 的 {:ts}。

_AMPM_TIME_RE = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
    r"(?:\s*(?P<ampm>[AaPp][Mm]))?"
    r"(?:\s*(?P<tzsign>[+-])(?P<tzhour>\d{1,2}):?(?P<tzminute>\d{2}))?"
)


# 捕获模式不带命名组(同模板可重复使用)。
_AMPM_TIME_PATTERN = (
    r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?(?:\s*[+-]\d{1,2}:?\d{2})?"
)


def _parse_ampm_time(text: str) -> time:
    """带 AM/PM 与可选时区的时刻(见 ``AmPmTime``)。"""
    match = _AMPM_TIME_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"cannot parse {text!r} as a time")
    hour = int(match["hour"])
    if match["ampm"] is not None:
        hour %= 12
        if match["ampm"].upper() == "PM":
            hour += 12
    tzinfo = None
    if match["tzsign"] is not None:
        tzinfo = _timezone_from(match["tzsign"], match["tzhour"], match["tzminute"])
    return time(hour, int(match["minute"]), int(match["second"] or 0), tzinfo=tzinfo)


type AmPmTime = Annotated[
    time,
    Converter(_parse_ampm_time, pattern=_AMPM_TIME_PATTERN, name="AmPmTime"),
]
# 10:21:36 PM -5:30(AM/PM 与时区可选);对应 parse 的 {:tt}。

# --------------------------------------------------------------------- 数字


def _parse_comma_int(text: str) -> int:
    """千分位整数(``,`` 或 ``.`` 分隔)-> ``int``。"""
    return int(text.replace(",", "").replace(".", ""))


type CommaInt = Annotated[
    int,
    Converter(
        _parse_comma_int,
        pattern=r"[+-]?\d{1,3}(?:[.,]\d{3})+",
        name="CommaInt",
    ),
]
# 1,234,567 / 1.234.567 -> int(必须带千分位,与 parse 的 {:n} 一致)。


def _parse_percent(text: str) -> float:
    """百分数 ``12.5%`` -> ``0.125``。"""
    return float(text[:-1]) / 100


type Percent = Annotated[
    float,
    Converter(
        _parse_percent,
        pattern=r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)%",
        name="Percent",
    ),
]
# 12.5% -> 0.125;对应 parse 的 {:%}。


def _parse_hex_int(text: str) -> int:
    """十六进制整数 ``0x1F`` / ``FF`` -> ``int``。"""
    return int(text, 16)


type HexInt = Annotated[
    int,
    Converter(
        _parse_hex_int,
        pattern=r"[+-]?(?:0[xX])?[0-9a-fA-F]+",
        name="HexInt",
    ),
]
# 0x1F / FF -> 31 / 255(前缀可选,与 parse 的 {:x} 一致)。


def _parse_int(text: str) -> int:
    """十进制/``0x``/``0b``/``0o`` 前缀整数(前导零按十进制,与 parse 一致)。"""
    sign = -1 if text.startswith("-") else 1
    body = text.lstrip("+-")
    bases = {"0x": 16, "0o": 8, "0b": 2}
    base = bases.get(body[:2].lower(), 10)
    return sign * int(body[2:] if base != 10 else body, base)


type Int = Annotated[
    int,
    Converter(
        _parse_int,
        pattern=r"[+-]?(?:0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|\d+)",
        name="Int",
    ),
]
# 42 / 0x1F / 0b101 / -0o17(支持进制前缀,042 按十进制);对应 parse 的 {:d}。


def _parse_binary(text: str) -> int:
    """二进制整数,前缀可选。"""
    return int(text, 2)


type Binary = Annotated[
    int,
    Converter(_parse_binary, pattern=r"[+-]?(?:0[bB])?[01]+", name="Binary"),
]
# 0b101 / 101;对应 parse 的 {:b}。


def _parse_octal(text: str) -> int:
    """八进制整数,前缀可选。"""
    return int(text, 8)


type Octal = Annotated[
    int,
    Converter(_parse_octal, pattern=r"[+-]?(?:0[oO])?[0-7]+", name="Octal"),
]
# 0o17 / 17;对应 parse 的 {:o}。


type Float = Annotated[
    float,
    Converter(float, pattern=r"[+-]?(?:\d+\.\d+|\.\d+)", name="Float"),
]
# 1.5 / .5(必须带小数点;"1" 与 "1." 不匹配,与 parse 的 {:f} 一致)。


def _parse_exponent_float(text: str) -> float:
    """科学计数法 ``float``(``NAN`` / ``INF`` 等大小写不敏感)。"""
    return float(text.lower())


type ExponentFloat = Annotated[
    float,
    Converter(
        _parse_exponent_float,
        pattern=r"[+-]?(?:(?:\d+(?:\.\d+)?|\.\d+)[eE][+-]?\d+|nan|inf(?:inity)?)",
        flags=re.IGNORECASE,
        name="ExponentFloat",
    ),
]
# 1.1e-10 / -1.1E+3 / NAN(必须带指数,与 parse 的 {:e} 一致)。


type GeneralFloat = Annotated[
    float,
    Converter(
        float,
        pattern=r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?",
        name="GeneralFloat",
    ),
]
# 42 / 1.5 / 4.2e1,统一转 float;对应 parse 的 {:g}。


type DecimalNumber = Annotated[
    Decimal,
    Converter(Decimal, pattern=r"[+-]?(?:\d+\.\d+|\.\d+)", name="DecimalNumber"),
]
# 1.5 -> decimal.Decimal;对应 parse 的 {:F}。
