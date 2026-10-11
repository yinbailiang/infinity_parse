# Scanner 扫描器——扫描入口与字段声明

## 概述

`scanner` 模块是 InfinityParse 的门面：把模板与转换器类型绑定成可复用解析器，并提供
三种匹配模式。类型参数同时决定字段的转换方式——每个类型参数解析为一条或多条转换器
分支，按声明顺序竞争。

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
```

---

## 入口一览

| 入口 | 调用形态 | 语义 | 返回 |
| - | - | - | - |
| `scan[Meta]` | `scan[int]("{}")("42")` | 全串匹配（先 strip 输入） | `tuple[*Meta]` |
| `search[Meta]` | `search[int]("{}")("a 42 b")` | 输入中首个匹配 | `tuple[*Meta] \| None` |
| `scanall[Meta]` | `scanall[int]("{}")("1 2 3")` | 所有不重叠匹配，从左到右 | `list[tuple[*Meta]]` |
| `Scanner[Meta]` | `Scanner[int]("{}")` | 同上三种，暴露为实例方法 | `Scanner` 实例 |

`Scanner` 实例方法与方法对应关系：

| 方法 | 等价入口 | 说明 |
| - | - | - |
| `fullmatch(input_value)` | `scan[...]` | 模板必须覆盖整个（已 strip 的）输入，否则 `MatchError` |
| `search(input_value)` | `search[...]` | 无匹配返回 `None` |
| `findall(input_value)` | `scanall[...]` | 无匹配返回空列表 |

### 签名

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

> `scan[int]` 返回一个真实的泛型别名（`types.GenericAlias` 子类）：
> `get_origin(scan[int]) is scan`、`get_args(scan[int]) == (int,)`；对别名调用
> `(template)` 才构建解析器。不同订阅之间状态互相独立，可放心复用。

### 三种模式的行为差异

```python
from typing import Annotated

from infinity_parse import Converter, scan, scanall, search

Number = Annotated[int, Converter(int, pattern=r"\d+")]

scan[Number]("{}")("42")  # (42,)
search[Number]("{}")("answer 42")  # (42,) —— 首个匹配
scanall[Number]("{}")("1 2 3")  # [(1,), (2,), (3,)] —— 全部匹配
search[Number]("{}")("nothing")  # None
```

- `scan`：先对整串输入 strip，再要求模板覆盖全部文本。
- `search` / `scanall`：对原始输入扫描（不 strip 外层空白）。
- 三种模式下，转换器失败都以 `ConvertError` 中止——`search` / `scanall` 不会跳过
  失败项去尝试后面的匹配。

---

## 模板语法

模板由字面文本与 `{}` 占位符组成：

| 写法 | 含义 |
| - | - |
| `{}` | 一个字段，默认捕获模式 `.+?`（非空、单行、惰性） |
| `{{` / `}}` | 字面花括号 `{` / `}` |
| 空白串 | 匹配任意空白串（`\s+`），换行也算 |
| 单个 `{` 或 `}` | 构造时抛 `ValueError` |

```python
scan[int]("{{}}={}")("{}= 42")  # (42,)
scan[int]("{{{}}}")("{42}")  # (42,)
scan[int]("{ x }")  # ValueError: single '{' in template ...
```

- 输入两端的空白被忽略，每个捕获字段的文本默认也会被 strip
  （可用 `Converter(strip=False)` 关闭，见 [engine.md](engine.md)）。
- 模板中的空白是宽松的：`"x={}, y={}"` 能匹配 `"x= 1,   y=2"`。
- 字段默认模式不跨行；输入含换行时，交给相邻字段间的 whitespace 分隔消化
  （如 `"1\nhello"` 匹配 `"{} {}"`）。

---

## 声明字段

每个类型参数的解析规则：若注解携带 `Converter` 规格（spec），使用该规格；否则回退到
「默认分支」——能在内置表中找到的用内置转换器，找不到的就把类型本身当转换器调用。

### 内置默认

| 声明 | 转换方式 | 示例 |
| - | - | - |
| `bool` | `true` / `false` / `1` / `0`（大小写不敏感） | `scan[bool]("{}")("true")` → `(True,)` |
| `dict` / `list` / `tuple` / `set` / `frozenset`（含泛型形态） | `ast.literal_eval`（Python 字面量语法） | `scan[list[int]]("{}")("[1, 2, 3]")` → `([1, 2, 3],)` |
| 其它可调用类型 | 直接调用：`int` / `float` / `str` 等 | `scan[int]("{}")("42")` → `(42,)` |
| 自定义类 | 把该类当转换器调用 | `scan[Hex]("{}")("ff")` → `Hex("ff")` |

```python
from infinity_parse import scan

scan[dict[str, str]]("{}")('{"key": "value"}')  # ({"key": "value"},)
scan[tuple[int, str]]("{}")("(1, 'a')")  # ((1, "a"),)
```

容器按 Python 字面量解析，`{'a': 0x10}` 也成立（十六进制按 Python 语法处理）。

### Annotated[T, Converter(...)]

用 `typing.Annotated` 给字段附加转换器规格：自定义捕获模式、显示名、`strip` 开关与
`re` 标志（参数细节见 [engine.md](engine.md)）。

```python
from typing import Annotated

from infinity_parse import Converter, scan

parse = scan[
    Annotated[int, Converter(int, pattern=r"\d+", name="age")],
    Annotated[str, Converter(str, pattern=r'"[^"]*"', name="name")],
]("age={} name={}")

parse('age=42 name="kim"')  # (42, '"kim"')
```

规则细节：

- 规格替换默认分支；`Annotated` 里的其它元数据（如文档字符串）被忽略。
- 嵌套的 `Annotated` 会拍平成一层：`Annotated[Annotated[int, C], "doc"]` 等价于
  `Annotated[int, C]`。
- PEP 695 `type` 别名在运行时展开，与类型检查器的展开方式一致（别名链递归展开，
  `type MyInt = int` 这类平铺别名同样适用）。

```python
type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,)
```

### OneOf——竞争分支

一个字段可以打包多条分支：`Annotated[T, OneOf[C1, C2]]`。分支按声明顺序尝试；首个
「模式匹配」的分支立即生效——若其转换器随后失败，整个扫描以 `ConvertError` 中止，
**绝不回退到后面的分支**。

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

| 规则 | 行为 |
| - | - |
| 分支竞争 | 首个模式匹配的分支胜出（即使后面的分支也能匹配） |
| 转换失败 | 硬失败：中止并抛 `ConvertError`，不回退 |
| `OneOf[非 Converter]` | 构造时抛 `TypeError` |
| `OneOf[()]`（空分支） | 构造时抛 `TypeError` |
| 直接调用 `OneOf()` | 抛 `TypeError`（必须使用订阅语法） |

### 联合类型糖

由 `Annotated` 成员组成的 `|` 联合是同一竞争的语法糖：按成员顺序展开为分支组；没有
规格的成员回退为默认分支。

```python
parse_number = scan[
    Annotated[int, Converter(int, pattern=r"\d+")]
    | Annotated[float, Converter(float, pattern=r"\d+\.\d+")]
]("{}")

parse_number("42")  # (42,)
parse_number("3.14")  # (3.14,)
```

- 成员自带 `OneOf` 时，整组按成员顺序参与竞争。
- 规格加在「包裹整个联合」的 `Annotated` 上时，它作为一个分支组整体绑定；此时若成员
  又自带规格，构造时抛 `ValueError`（歧义）。
- 联合的别名成员（如 `type Digits = ...`）同样会展开。

```python
# 规格绑定整个联合：合法
scan[Annotated[int | str, Converter(int, pattern=r"\d+")]]("{}")("42")  # (42,)

# 外层规格 + 成员规格：ValueError
scan[
    Annotated[
        Annotated[int, Converter(int, pattern=r"\d+")] | str,
        Converter(str, name="outer"),
    ]
]("{}")
```

### 单层规则

**一个字段的所有分支必须位于同一层 `Annotated`，并打包进同一个 `OneOf`。** 外层无法
覆盖内层；隐藏在与别名深处的规格混写会产生歧义——跨层混写一律在构造时报错：

```python
type Age = Annotated[int, Converter(int, pattern=r"\d+", name="age")]

scan[Age]("{}")("42")  # (42,) —— 合法

scan[Annotated[Age, Converter(int, name="outer")]]("{}")
# ValueError: multiple Converter specs on one field; pack competing branches
#   in OneOf[*Converter], e.g. Annotated[T, OneOf[C1, C2]]
```

同一层出现多个裸 `Converter`（未打包）同样被拒绝：

```python
scan[
    Annotated[
        str,
        Converter(str, pattern=r"\d+"),
        Converter(str, pattern=r"[a-z]+"),  # ValueError
    ]
]("{}")
```

### 低层解析

想在代码里手动解析注解时，使用 `resolve_field(declared, convs)`——把「声明类型 +
转换器列表」解析为 `Field`（配合 `Template` 可直接构建低层解析器，见
[engine.md](engine.md)）：

```python
from infinity_parse import Converter, resolve_field

field = resolve_field(dict, [Converter(lambda raw: raw, name="raw")])
field.converters[0].fn  # <lambda>
```

---

## 强类型结果

结果元组的类型与类型参数一一对应，pyright 可直接推导：

```python
import json
from typing import Annotated, assert_type

from infinity_parse import Converter, scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
assert_type(a, int)  # pyright 检查通过
assert_type(b, float)
assert_type(scan[int, int]("{} {}")("7 8"), tuple[int, int])
assert_type(
    scan[Annotated[dict[str, str], Converter(json.loads)]]("{}")('{"k": "v"}'),
    tuple[dict[str, str]],
)
```

## 复用解析器

解析器构建一次，可反复使用；不同订阅互相独立：

```python
parse_pair = scan[int, int]("{} {}")
parse_pair("7 8")  # (7, 8)
parse_pair("9 10")  # (9, 10)
```

## 注意事项

- `scan[...]` 至少需要一个转换器类型：直接调用 `scan(...)` 或空订阅都会抛
  `TypeError`；零字段模板请直接使用 `Template`（见 [engine.md](engine.md)）。
- 模板中的 `{}` 个数必须与类型参数个数一致，否则构造时抛 `ValueError`
  （`scan[int]("hello")` 即为例）。
- 转换器必须可调用且可哈希（参与编译缓存）。
- `MatchError` 表示「没匹配上」；`ConvertError` 表示「匹配上了但转换失败」，二者
  语义不可混用（见 [engine.md](engine.md)）。
