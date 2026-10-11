# InfinityParse

**强类型、`scanf` 风格的 Python 字符串解析库。**

InfinityParse 把每个 `{}` 占位符与一个转换器类型一一对应：`scan[int, float]("{} {}")`
中的类型参数声明字段的转换方式，调用解析器并传入输入，即可得到强类型元组。
零运行时依赖，面向 Python 3.14+（PEP 695 泛型语法）。

## 安装

```bash
# uv（推荐）
uv add infinity_parse

# 或 pip
pip install infinity_parse
```

## 快速入口

- [核心总览](infinity_parse.md) — 扫描流程与组件关系
- [Scanner 扫描器](scanner.md) — 三种匹配模式、模板语法与字段声明
- [Engine 引擎](engine.md) — `Converter` 字段级配置、`Template` 编译与错误模型
- [精选类型（parse_types）](parse_types.md) — 日期时间 / 数字 / 字符类开箱即用
- [组合子（combinators）](combinators.md) — 把扫描器组合成更大的解析器
- [README（快速开始）](https://github.com/yinbailiang/infinity_parse/blob/main/README_zh.md)

## 最简示例

```python
from infinity_parse import scan

a, b, c = scan[int, float, str]("{} {} {}")("1 2.5 hello")
# a=1 (int), b=2.5 (float), c="hello" (str)
```
