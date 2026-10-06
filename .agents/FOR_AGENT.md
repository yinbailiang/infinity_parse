# FOR AGENT — 智能体行为指引

## 项目概述

**infinity_parse** — 强类型、scanf 风格的字符串解析库（Python 3.14+）。

## 开发工具链

**本项目唯一合法的 Python 工具链是 [uv](https://docs.astral.sh/uv/)。**

- 所有 Python 命令必须通过 `uv run` 执行
- 执行任何代码修改前，先确认 uv 可用：`uv --version`
- 若 uv 缺失，提示用户安装 [uv](https://docs.astral.sh/uv/)，不得绕过
- 首次设置开发环境：

  ```bash
  uv sync --extra dev && uv run pre-commit install
  ```

## 信息源

以下文件是项目真相的权威来源。**不确定任何配置、数值或结构时，直接阅读对应文件，禁止猜测。**

| 信息 | 来源 |
| --- | --- |
| 项目元数据、依赖、工具配置 | `pyproject.toml` |
| 对外说明与用法 | `README.md` |
| 实际代码结构与实现 | `src/infinity_parse/` |
| 测试范例与共享 fixture | `tests/` |
| `example/example.py` | 可运行示例与验证入口 |
| `example/moe_calc.py` | moe_calc 计算器示例与验证入口 |
| `example/dice_catgirl.py` | 骰子猫娘示例与验证入口 |
| `example/simple_kv.py` | KV 解析器示例与验证入口 |

## 变更铁律

**每一项代码变更必须依次完成以下三步，缺一不可：**

1. **改代码** — 修改 `src/infinity_parse/` 中的实现
2. **写测试** — 在 `tests/` 镜像路径下编写对应测试，覆盖新功能/边界/异常
3. **同步文档** — 更新 docstring、README 与 `__all__` 导出

> 提交前运行 pre-commit-check 技能验证全部通过。

## 不可妥协的原则

以下原则为项目根基，任何情况下不得违反：

1. **Pyright strict 零遮蔽** — `src/infinity_parse/` 目录下绝对禁止 `# type: ignore` 或 `# pyright: ignore` 注释
2. **完整类型注解** — 所有公开 API 必须有完整参数、返回值、泛型注解
3. **镜像测试** — `tests/` 目录结构与 `src/infinity_parse/` 一一对应

## 代码约定

以下约定应遵守，具体参数以 `pyproject.toml` 为准：

- 日志通过 `logging.getLogger(__name__)` 获取；内部细节用 `debug`，异常用 `warning`
- 内部状态通过 `@property` 暴露，避免直接访问私有字段
- **注释只解释「为什么」，不解释「做什么」**——一眼能看懂的代码逻辑不写注释
- **docstring 只描述公开行为**（用途、参数、返回值、异常），不描述内部实现流程
- **所有 Python 命令必须通过 `uv run` 执行**（如 `uv run pytest`）；禁止裸调 Python 命令
- 工具链：ruff（lint + format）、pyright（类型检查）、pytest（测试）
- 提交消息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)

---

## SKILLS

具体编码任务的详细操作指引独立存放在 `.agents/SKILLS/` 目录中。
执行对应任务时，**必须阅读对应的 SKILL 文件**。

| 任务 | SKILL 文件 |
| --- | --- |
| 修改核心 API | [modify-core-api.md](SKILLS/modify-core-api.md) |
| 审查前检查 | [pre-commit-check.md](SKILLS/pre-commit-check.md) |
| 编写测试 | [write-tests.md](SKILLS/write-tests.md) |
| 编写文档 | [write-docs.md](SKILLS/write-docs.md) |
| 创建通用技能 | [write-skill.md](SKILLS/write-skill.md) |
| 项目发布 | [publish.md](SKILLS/publish.md) |
