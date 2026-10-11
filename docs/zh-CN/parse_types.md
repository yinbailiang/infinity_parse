# 精选类型（parse_types）

## 概述

`infinity_parse.parse_types` 提供一批开箱即用的转换器类型（`Annotated` 别名），命名与
语义对齐 `parse` 库的格式符（`{:d}`、`{:%Y-%m-%d}` 等）。全部类型都只是普通的类型
别名，直接放进 `scan[...]` 的类型参数即可：

```python
from infinity_parse import scan
from infinity_parse import parse_types as t

scan[t.Int, t.SimpleDate]("{} {}")("42 2024-01-15")  # (42, date(2024, 1, 15))
```

---

## 字符类

| 类型 | 输入示例 | 结果 | 对应 parse | 说明 |
| - | - | - | - | - |
| `t.Letters` | `abcXYZ` | `"abcXYZ"` | `{:l}` | 纯 ASCII 字母（`[a-zA-Z]+`） |
| `t.Word` | `a_1` | `"a_1"` | `{:w}` | 字母、数字、下划线（`\w+`） |
| `t.NonWord` | `!!` | `"!!"` | `{:W}` | 非 `\w` 字符（`\W+`） |
| `t.Whitespace` | `"   "` | `"   "` | `{:s}` | 保留原始空白（`strip=False`） |
| `t.NonWhitespace` | `x` | `"x"` | `{:S}` | 非空白（`\S+`） |
| `t.NonDigit` | `x` | `"x"` | `{:D}` | 非数字（`\D+`） |

> `t.Whitespace` 有两个使用要点：字段保留原始空白（不 strip）；但 `scan` 会先 strip
> 整个输入，纯空白输入需要使用 `scanall` / `search`（它们不 strip 输入）。

```python
from infinity_parse import scanall
from infinity_parse import parse_types as t

scanall[t.Whitespace]("{}")("a  b")  # [("  ",)]
```

## 日期与时间

| 类型 | 输入示例 | 结果 | 对应 parse |
| - | - | - | - |
| `t.SimpleDate` | `2024-01-15` | `date(2024, 1, 15)` | `{:%Y-%m-%d}` |
| `t.SimpleTime` | `12:30` / `12:30:45` | `time(12, 30)` / `time(12, 30, 45)` | `{:%H:%M}` 一族 |
| `t.IsoDateTime` | `2024-01-15T12:30:45+08:00` | 带时区 `datetime` | `{:ti}` |
| `t.Rfc2822DateTime` | `Mon, 20 Jan 1972 10:21:36 +1000` | 带时区 `datetime` | `{:te}` |
| `t.GlobalDate` | `20/1/1972 10:21:36 AM +1:00` | `datetime` | `{:tg}` |
| `t.UsDate` | `1/20/1972 10:21:36 PM +10:30` | `datetime` | `{:ta}` |
| `t.CtimeDateTime` | `Sun Sep 16 01:03:52 1973` | `datetime` | `{:tc}` |
| `t.HttpLogDateTime` | `21/Nov/2011:00:07:11 +0000` | 带时区 `datetime` | `{:th}` |
| `t.SyslogDateTime` | `Nov 9 03:37:44` | `datetime`（补当前年） | `{:ts}` |
| `t.AmPmTime` | `10:21:36 PM` / `10:21` | `time`（AM/PM 与时区可选） | `{:tt}` |

- `t.GlobalDate` / `t.UsDate` 的日期部分必填，时间、AM/PM 与时区偏移均可选；
  12 小时制会自动换算（`PM` 加 12 小时）。
- `t.IsoDateTime` 接受 `T` 或空格分隔、可省略秒、支持 `Z` 后缀与 `+08:00` 偏移。

## 数字

| 类型 | 输入示例 | 结果 | 对应 parse | 说明 |
| - | - | - | - | - |
| `t.CommaInt` | `1,234,567` / `1.234.567` | `1234567` | `{:n}` | 必须带千分位分隔符 |
| `t.Percent` | `12.5%` / `-.5%` | `0.125` / `-0.005` | `{:%}` | 百分数转小数 |
| `t.HexInt` | `0x1F` / `FF` | `31` / `255` | `{:x}` | 前缀可选 |
| `t.Int` | `42` / `-0x1F` / `0b101` / `-0o17` | `42` / `-31` / `5` / `-15` | `{:d}` | 支持 `0x` / `0b` / `0o` 前缀；`042` 按十进制 |
| `t.Binary` | `0b101` / `101` | `5` | `{:b}` | 前缀可选 |
| `t.Octal` | `0o17` / `17` | `15` | `{:o}` | 前缀可选 |
| `t.Float` | `-1.5` / `.5` | `-1.5` | `{:f}` | 必须带小数点（`1`、`1.` 不匹配） |
| `t.ExponentFloat` | `1.1e-10` / `NAN` / `INF` | `1.1e-10` | `{:e}` | 必须带指数；特殊值大小写不敏感 |
| `t.GeneralFloat` | `42` / `1.5` / `4.2e1` | `42.0` | `{:g}` | 统一转 `float` |
| `t.DecimalNumber` | `1.5` | `Decimal("1.5")` | `{:F}` | 必须带小数点，返回 `decimal.Decimal` |

## 从字面量构建类型

两个泛型构建器可以把「字面模式 / 字面格式串」直接变成类型。

### RegexString

`t.RegexString[Literal[pattern]]` 在运行时解析为
`Annotated[str, Converter(str, pattern=...)]`；类型检查器看到的是携带模式的 `str`
子类型，默认 `str` 的行为不受影响。

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import RegexString

type DashPair = RegexString[Literal[r"\d+-\d+"]]

scan[DashPair]("{}")("12-34")  # ('12-34',)
```

### DateTime

`t.DateTime[Literal[fmt]]` 由 `strptime` 格式串推导捕获模式，转换时用同一格式串解析：

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import DateTime

type LogStamp = DateTime[Literal["%Y-%m-%d %H:%M:%S"]]

scan[LogStamp]("{}")("2024-01-15 12:30:45")
# (datetime(2024, 1, 15, 12, 30, 45),)
```

已内置的 `t.CtimeDateTime` 与 `t.HttpLogDateTime` 正是这类别名：
`DateTime[Literal["%a %b %d %H:%M:%S %Y"]]` 与
`DateTime[Literal["%d/%b/%Y:%H:%M:%S %z"]]`。

支持的指令为常用子集：`a A b B d f H I j m M p S y Y z Z %`；不支持的指令
（如 `%Q`）在构造时抛 `TypeError`。

## 使用示例

```python
from infinity_parse import scan
from infinity_parse import parse_types as t

# 混用内置类型与精选类型
scan[t.Int, t.Percent]("{} {}")("42 12.5%")  # (42, 0.125)

# 同一模板重复使用同一种类型（捕获模式内不含命名分组，不会冲突）
scan[t.SimpleDate, t.SimpleDate]("{} {}")(
    "2024-01-15 2025-02-03"
)  # (date(2024, 1, 15), date(2025, 2, 3))
```

## 注意事项

- `t.SyslogDateTime` 的 syslog 时间戳不带年份：转换器补**当前年份**
  （与 `parse` 一致）。
- `t.Whitespace` 保留原始空白，但 `scan` 先 strip 整个输入：纯空白输入请使用
  `scanall` / `search`。
- `t.Float`、`t.DecimalNumber` 必须带小数点；`t.CommaInt` 必须带千分位——这些
  「严格性」与 `parse` 的对应格式符一致。
- 校验失败分两层：模式不匹配 → `MatchError`；模式匹配但值非法（如 `2024-13-45`）
  → `ConvertError`。
- 精确匹配语义随所选的 `scan` / `search` / `scanall` 模式（见 [scanner.md](scanner.md)）。
