# 组合子（combinators）

## 概述

`combinators` 模块提供五个组合原语，把扫描器与普通可调用对象拼成更大的解析器。核心
抽象是：

```python
type Parser[T] = Callable[[str], T]
```

扫描器本身就是 `Callable[[str], tuple[...]]`——配合 `first_field` 即可放进组合子。
所有组合子只把 `MatchError`（不匹配）当作「可以继续尝试」，其余异常照常冒泡。

```python
from infinity_parse import alt, first_field, scan

value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
value('"hi"')  # 'hi'
value("hi")  # 'hi'
```

---

## alt——有序选择

```python
def alt[T](*parsers: Parser[T]) -> Parser[T]
```

按顺序尝试解析器，返回第一个不抛 `MatchError` 的结果：

- 只有 `MatchError` 会触发「换下一个」；`ConvertError` 等异常立即中止（硬失败不吞）。
- 全部失败时抛出 `MatchError("no alternative matched ...")`，`__cause__` 指向最后
  一次失败。

```python
from infinity_parse import ConvertError, MatchError, alt, scan

value = alt(scan[int]("x={}"), scan[int]("y={}"))
value("z=1")  # MatchError: no alternative matched 'z=1'

strict = alt(scan[int]("{}"), scan[str]("{}"))
strict("abc")  # ConvertError —— int 分支匹配成功但转换失败，不会回退到 str
```

## recursive——不动点（递归）

```python
def recursive[T](builder: Callable[[Parser[T]], Parser[T]]) -> Parser[T]
```

`builder` 收到一个指向「最终解析器」的 thunk，用来构造自引用文法：

```python
from infinity_parse import MatchError, Parser, alt, first_field, recursive, scan


def wrapped(build: Parser[str]) -> Parser[str]:
    def group(text: str) -> str:
        if not (text.startswith("(") and text.endswith(")")):
            raise MatchError(f"not wrapped: {text!r}")
        return build(text[1:-1])

    return alt(group, first_field(scan[str]("{}")))


parse = recursive(wrapped)
parse("(((x)))")  # 'x'
parse("x")  # 'x'
```

> 嵌套深度受解释器递归上限约束：默认设置下大约 300-350 层（每层约 3 帧）；极深的
> 文法需要 `sys.setrecursionlimit`（过深有栈溢出风险）。

## split_top——顶层拆分

```python
def split_top(separator: str, delimiters: tuple[str, str]) -> Parser[list[str]]
```

按「顶层」分隔符拆分字符串：`delimiters`（开 / 闭字符集合）保护嵌套文本里的分隔符。
返回原始片段列表（不 strip、不解析）：

```python
from infinity_parse import split_top

split_commas = split_top(",", ("[{", "}]"))
split_commas("1, [2, 3], {4, 5}")  # ['1', ' [2, 3]', ' {4, 5}']
```

- 深度按字符计数：开集合里任何字符 `+1`，闭集合里任何字符 `-1`；只有传入的字符会被保护（`("[{", "}]")` 保护 `[]` 与 `{}`，不含圆括号——需要时传入 `("([{", ")]}")`）。
- 分隔符只在深度为 0 时生效；不做引号感知。
- 空输入返回 `['']`。

## sep_by——分隔列表

```python
def sep_by[T](parser: Parser[T], spliter: Parser[list[str]]) -> Parser[list[T]]
```

先用 `spliter`（通常来自 `split_top`）拆分，再对每个片段应用 `parser`：

```python
from infinity_parse import first_field, scan, sep_by, split_top

split_commas = split_top(",", ("[{", "}]"))
numbers = sep_by(first_field(scan[int]("{}")), split_commas)
numbers("1, 2, 3")  # [1, 2, 3]
```

## first_field——适配扫描器

```python
def first_field[T, *Ts](parser: Parser[tuple[T, *Ts]]) -> Parser[T]
```

把「返回元组的扫描器」适配成「返回首字段的普通解析器」，以便放进 `alt` /
`sep_by` / `recursive`：

```python
value = alt(first_field(scan[str]('"{}"')), first_field(scan[str]("{}")))
```

## 组合实战

`example/example.py` 用这些原语搭了一个递归的节点解析器：每个节点由若干「带模式的
分支」竞争（对象 / 数组 / 原子），子节点通过 `recursive` 的 thunk 递归解析：

```python
# 摘自 example/example.py（节选）
def build_node(self: Parser[Any]) -> Parser[Any]:
    def parse_pair(member: str) -> tuple[str, Any]:
        key, _, raw = member.partition(":")
        return key.strip(), self(raw)

    split_commas = split_top(",", ("[{", "}]"))
    pairs = sep_by(parse_pair, split_commas)
    members = sep_by(self, split_commas)
    ...
    node = scan[
        Annotated[
            Any,
            OneOf[
                Converter(to_object, pattern=r"\{.+\}", name="object"),
                Converter(to_array, pattern=r"\[.+\]", name="array"),
                Converter(to_atom, pattern=r"^\w+$", name="atom"),
            ],
        ]
    ]("{}")

    return first_field(node)
```

完整可运行版本见仓库的 `example/example.py`、`example/moe_calc.py` 与
`example/dice_catgirl.py`。

## 注意事项

- 组合子只区分「`MatchError` = 不匹配」与「其它异常 = 硬失败」；转换器抛出的
  `ConvertError` 会穿透 `alt`——这是刻意设计。
- `recursive` 的 thunk 只在 `builder` 返回之后被调用；提前调用会触发
  `AssertionError`。
- `split_top` 不做空白修剪：实际使用时通常靠成员解析器自身消化空白
  （如 `first_field(scan[int]("{}"))` 会 strip 捕获字段）。
- 组合子直接处理传入的整串文本，是否允许残留片段由你的解析器决定——组合子不做
  全串校验（`scan` 自身会做）。
