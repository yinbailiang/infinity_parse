# infinity_parse

强类型、`scanf` 风格的 Python 字符串解析库，要求 Python 3.14+。
以 `infinity_parse` 发布与导入。

每个 `{}` 占位符对应一个转换器类型，作为类类型参数传入；随后以调用参数传入
模板与输入字符串：

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
# a=1 (int), b=2.5 (float), c="hello" (str)
```

解析器可复用：

```python
parse_pair = scan[int, int]("{} {}")
parse_pair("7 8")  # (7, 8)
```

> 📖 [English](README.md) · 🌐 [在线文档](https://yinbailiang.github.io/infinity_parse/)

## 内置转换器

内置泛型容器（`dict`、`list`、`tuple`、`set` 与 `frozenset`）按 Python 字面量
通过 `ast.literal_eval` 解析；`bool` 接受 `true` / `false` / `1` / `0`
（大小写不敏感）：

```python
from infinity_parse import scan

scan[bool]("{}")("true")  # (True,)
scan[list[int]]("{}")("[1, 2, 3]")  # ([1, 2, 3],)
```

需要 JSON 专有语法（`true`、`false`、`null`）或任何自定义转换时，附加
`Converter` 规格即可：

```python
import json
from typing import Annotated

from infinity_parse import Converter, scan

parse_json = scan[Annotated[dict[str, str], Converter(json.loads)]]("{}")
parse_json('{"key": "value"}')  # ({"key": "value"},)
```

## 字段级配置

字段级配置以 `Converter` 元数据的形式携带在 `typing.Annotated` 里：转换函数、
捕获模式、strip 开关、`re` 标志与显示名：

```python
from typing import Annotated

from infinity_parse import Converter, scan

parse = scan[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
]("age={} name={}")
parse('age=42 name="kim"')  # (42, '"kim"')
```

包裹转换器的 `typing.Annotated` 会被剥离；其中的元数据除非包含 `Converter`
规格，否则一律忽略。竞争分支需显式打包进 `OneOf`：每条分支携带自己的模式，
首个模式匹配的分支胜出；若该分支随后转换失败，整个扫描失败——失败的转换器
绝不会回退到后面的分支：

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

同一字段上的多个裸 `Converter` 规格会被拒绝：**所有分支必须位于同一层
`Annotated`，并打包进同一个 `OneOf`**——跨层混写同样被拒绝，见
[所有分支必须位于同一层](#所有分支必须位于同一层)。

由 `Annotated` 成员组成的 `|` 联合是同一竞争的语法糖：每个成员按顺序成为一个
分支组；没有 `Converter` 的成员回退到默认分支：

```python
from typing import Annotated

from infinity_parse import Converter, scan

parse_number = scan[
    Annotated[int, Converter(int, pattern=r"\d+")]
    | Annotated[float, Converter(float, pattern=r"\d+\.\d+")]
]("{}")
parse_number("42")  # (42,)
parse_number("3.14")  # (3.14,)
```

加在「包裹整个联合」的 `Annotated` 上的规格会把联合整体绑定为一个分支组；
把它与成员上的规格组合是构造期错误。

转换器还可以随 PEP 695 `type` 别名一起传递；别名在运行时与类型检查器的静态
展开完全一致——别名链同样展开，平铺别名（`type MyInt = int`）也能通过：

```python
from typing import Annotated

from infinity_parse import Converter, scan

type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,)
```

### 所有分支必须位于同一层

**一个字段的所有分支必须位于同一层 `Annotated`，并打包进同一个 `OneOf`。**
外层无法覆盖内层，而藏在别名深处的规格在调用点通常不可见——因此跨层混写一律
在构造时被拒绝：

```python
from typing import Annotated

from infinity_parse import Converter, scan

type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,)
scan[Annotated[Age, Converter(int, name="outer")]]("{}")
# ValueError: multiple Converter specs on one field; pack competing branches
#   in OneOf[*Converter], e.g. Annotated[T, OneOf[C1, C2]]
```

同一条规则也拒绝「把规格加在包裹联合的 `Annotated` 上、同时又在成员上加了
规格」的写法——请把每条分支都声明在成员上
（`Annotated[int, C1] | Annotated[str, C2]`）。

### 转义字符串

给带引号的字符串字段扩展模式即可让它感知转义；转换器负责解码捕获的文本：

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

`(?:[^"\\]|\\.)*` 把 `\"` 视为转义对，因此字符串只会结束在未转义的引号处。
`json.loads` 解码捕获文本，并以硬失败 `ConvertError` 拒绝非法转义（绝不静默）。

## 精选类型

`infinity_parse.parse_types` 为常见文本形态提供了现成的转换器，对齐
`std::scan` 风格的格式符：

```python
from infinity_parse import parse_types as t
from infinity_parse import scan

scan[t.Int, t.SimpleDate]("{} {}")("42 2024-01-15")  # (42, date(2024, 1, 15))
scan[t.Percent]("{}")("12.5%")  # (0.125,)
scan[t.AmPmTime]("{}")("10:21:36 PM")  # (time(22, 21, 36),)
```

需要一次性自定义形态时，用 `t.RegexString` 从字面模式构建类型——它在运行时
解析为 `Annotated` 转换器，而类型检查器看到的是一个 `str` 子类型：

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import RegexString

type DashPair = RegexString[Literal[r"\d+-\d+"]]

scan[DashPair]("{}")("12-34")  # ('12-34',)
```

同样的思路通过 `t.DateTime` 承载 `strptime` 格式串——捕获模式由格式串的
指令推导：

```python
from typing import Literal

from infinity_parse import scan
from infinity_parse.parse_types import DateTime

type LogStamp = DateTime[Literal["%Y-%m-%d %H:%M:%S"]]

scan[LogStamp]("{}")("2024-01-15 12:30:45")
# (datetime(2024, 1, 15, 12, 30, 45),)
```

内置类型中就有这样的别名——`t.CtimeDateTime` 即
`t.DateTime[Literal["%a %b %d %H:%M:%S %Y"]]`，`t.HttpLogDateTime` 即
`t.DateTime[Literal["%d/%b/%Y:%H:%M:%S %z"]]`。

类型集合覆盖字符类（`t.Letters`、`t.Word`……）、ISO 8601 / RFC 2822 / ctime /
HTTP 日志 / syslog 日期时间、千分位整数（`t.CommaInt`）、百分数、十六进制 /
二进制 / 八进制整数、浮点与 `Decimal`。两点提醒：`t.SyslogDateTime` 的时间戳
不带年份，转换器会补上当前年份（与 `parse` 一致）；`t.Whitespace` 保留原始
空白，但 `scan` 会先 strip 整个输入——纯空白输入需要使用 `scanall` /
`search`。

## 组合解析器

`infinity_parse.combinators` 用扫描器与普通可调用对象搭出更大的解析器
（全部从包根导出）：

* `alt(*parsers)` —— 有序选择；只有 `MatchError`（未匹配）会继续尝试，
  转换失败则中止。
* `recursive(builder)` —— 为可嵌套文法提供的不动点组合子。
* `split_top(separator, delimiters)` —— 构建拆分器：在顶层 `separator`
  字符处拆分，`delimiters`（开、闭字符集合）保护嵌套文本。
* `sep_by(parser, spliter)` —— 顶层分隔列表，每个成员用一个 `parser`。
* `first_field(parser)` —— 把扫描器适配成普通 `Parser[T]`
  （即 `Callable[[str], T]`），以便放进其它组合子。

```python
from infinity_parse import alt, first_field, scan, sep_by, split_top

value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
value('"hi"')  # 'hi'
value("hi")  # 'hi'

split_commas = split_top(",", ("[{", "}]"))
numbers = sep_by(first_field(scan[int]("{}")), split_commas)
numbers("1, 2, 3")  # [1, 2, 3]
```

`example/example.py` 与 `example/moe_calc.py` 用这些原语构建各自的递归文法。

## 模板语义

每个 `{}` 以默认模式 `.+?` 捕获：

* 非空：至少一个字符；
* 单行：绝不匹配换行；
* 惰性：取「让剩余模板仍能匹配的最短文本」。

`Converter` 规格可以按字段替换模式。

模板中的空白串匹配输入中的任意空白串；输入两端（以及每个捕获字段两端）的空白
被忽略。模板中的字面花括号写作 `{{` 与 `}}`；单个花括号是错误。

### 匹配模式

同一模板支持三种 `re` 风格模式，既可作为可调用入口——`scan`、`search` 与
`scanall`——也可作为基类 `Scanner` 实例的 `fullmatch`、`search` 与
`findall` 方法：

* `scan` —— 模板必须覆盖整个（已 strip 的）输入，否则抛 `MatchError`。
* `search` —— 输入中首个匹配，模板不匹配时返回 `None`。
* `scanall` —— 从左到右的全部不重叠匹配组成的字段元组列表；无匹配时为空。

`search` 与 `scanall` 按原样扫描输入（不做外层 strip）；转换失败与 `scan`
一样以硬失败 `ConvertError` 中止：

```python
from typing import Annotated

from infinity_parse import Converter, scan, scanall, search

Number = Annotated[int, Converter(int, pattern=r"\d+")]

scan[Number]("{}")("42")  # (42,)
search[Number]("{}")("answer 42")  # (42,)
scanall[Number]("{}")("1 2 3")  # [(1,), (2,), (3,)]
```
> **默认惰性提示**：裸类型字段保持默认模式 `.+?`，在 `search` 模式下会在第一个能
> 完成匹配的最短截断处停下——`search[int]("age={}")("age=42")` 得到 `(4,)`。需要
> 完整 token 时请使用显式 `Converter(pattern=...)` 或精选类型。

## 性能

解析 10 万条日志行（`2024-03-15 12:30:45 GET /api/items 200 1234 5678 0.123`——8 个
字段：日期、时间、两个单词、三个整数、一个浮点），各库均使用编译后可复用的解析器：

| 库 | 耗时 | 吞吐 | 每行 |
| - | - | - | - |
| **infinity_parse** | ~0.41 s | ~240k 行/s | ~4.2 µs |
| infinity_parse（仅匹配）¹ | ~0.06 s | ~1.7M 行/s | ~0.59 µs |
| temparse | ~1.08 s | ~92k 行/s | ~10.8 µs |
| parse | ~1.57 s | ~64k 行/s | ~15.7 µs |
| parse（仅匹配）¹ | ~0.08 s | ~1.3M 行/s | ~0.77 µs |

¹ 两组「仅匹配」均为不转换字段的下限：infinity_parse 用 `Scanner.raw_pattern`，
`parse` 用 `evaluate_result=False`；与其它行口径不同。

在该负载下约为 **temparse 的 2.6 倍、`parse` 的 3.8 倍**；两者「仅匹配」的速度
接近（~0.59 µs vs ~0.77 µs），差距来自转换环节：infinity_parse 转换并返回字段
后总计约 4.2 µs，而 `parse` 的 ~15.7 µs 大多花在字段转换与富 `Result` 对象上。

> 单机实测（3 轮取最优），CPython 3.14、Linux x86_64：infinity_parse 为本仓库当前
> 代码（2026-10），parse 1.22.3、temparse 1.0.0。微基准受环境影响较大，请以自己的
> 实际负载为准。
>
> 复现：`uv run --extra benchmark python benchmarks/compare.py`（脚本在
> [`benchmarks/`](benchmarks/) 目录）。
## 文档

完整双语文档（中文 / English）位于 [`docs/`](docs/)，并发布在
<https://yinbailiang.github.io/infinity_parse/>。

| 文档 | 内容 |
| - | - |
| [核心总览](docs/zh-CN/infinity_parse.md) | 扫描流程与组件关系 |
| [Scanner 扫描器](docs/zh-CN/scanner.md) | 入口、匹配模式、模板语法与字段声明 |
| [Engine 引擎](docs/zh-CN/engine.md) | `Converter` 配置、`Template` 与错误模型 |
| [精选类型](docs/zh-CN/parse_types.md) | 内置 `parse_types` 类型目录 |
| [组合子](docs/zh-CN/combinators.md) | 把扫描器组合成更大的解析器 |

## 开发

```bash
uv sync --extra dev
uv run pre-commit install             # 可选：每次提交时运行门禁
uv run pre-commit run --all-files     # 完整的本地门禁
```

门禁依次运行 ruff（lint + format）、pyright（strict）、interrogate（docstring
覆盖率）、带覆盖率下限的 pytest，以及 `example/` 冒烟运行。CI（GitHub
Actions）运行同样的门禁，外加 3 操作系统的测试矩阵。

`example/example.py` 收录了成体系的示例：字段定制、JSON 解析，以及用库组合子
（`recursive` / `sep_by`）构建的递归扫描器。`example/moe_calc.py` 是用同样
方式搭建的四则运算小计算器——它的数字字段在 `OneOf` 里打包了 `int` 与
`float` 两条转换分支；直接运行可看演示，加 `--repl` 进入交互模式。
`example/dice_catgirl.py` 是配套的骰子猫娘：读取桌游记号（`3d6+2`），为
`?` 前缀的表达式预测概率，并为每次掷骰配上吐槽——同样是演示模式，或
`--repl` 交互。
`example/simple_kv.py` 以 40 行收尾：一个 `key=value` 配置解析器——每个字段在
`OneOf` 里打包「转义字符串」与「裸串」两条分支，元数据随 PEP 695 `type`
别名传递。

## 许可证

[MIT](LICENSE.md)

## 属于 InfinitySystem

![icon](docs/res/infinity_icon/256x256.png)
