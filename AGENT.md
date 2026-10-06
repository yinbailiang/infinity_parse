# Agent Instructions

infinity_parse 为 AI 编程助手提供结构化的引导体系。
**在开始任何编码工作前，必须完整阅读 `.agents/` 目录下的所有指引文件。**

## 引导目录

```text
.agents/
├── FOR_AGENT.md                  # 通用行为准则与编码规范
├── SKILLS/                       # 任务技能
│   ├── modify-core-api.md        #   修改核心 API
│   ├── pre-commit-check.md       #   审查前检查
│   ├── write-tests.md            #   编写测试
│   ├── write-docs.md             #   编写文档
│   ├── write-skill.md            #   创建通用技能
│   └── publish.md                #   项目发布
├── MEMORY/
│   ├── MEMORY_RULE.md            # 记忆管理技能
│   └── memorys/                  #   运行时记忆存储（跨会话持久化）
└── TEMP_FILES/
    ├── TEMP_FILE_RULE.md         # 临时文件管理技能
    └── tmps/                     #   运行时临时文件存储（会话内有效）
```

### 各模块技能

| 模块 | 技能 | 持久性 |
| --- | --- | --- |
| `FOR_AGENT.md` | 编码铁律、类型安全、代码约定 | 静态规则 |
| `SKILLS/` | 修改核心 API、审查前检查、编写测试、编写文档、创建通用技能、项目发布 | 静态规则 |
| `MEMORY/` | 跨会话记忆：记住用户偏好、历史决策、已知问题 | 跨会话持久 |
| `TEMP_FILES/` | 临时产物管理：中间文件、草稿、调试输出 | 会话内有效 |

## 行为准则

- **需求不明确时**：先向用户确认具体要求，再动手执行
- **方案多选时**：列出可行方案，让用户选择，不自行决定

## 工作流程

1. **首先**，阅读 `.agents/FOR_AGENT.md`，掌握编码铁律与约定。
2. **其次**，阅读 `.agents/SKILLS/` 中对应任务的技能文件。
3. **然后**，阅读 `.agents/MEMORY/MEMORY_RULE.md` 和 `.agents/TEMP_FILES/TEMP_FILE_RULE.md`，了解运行时管理技能。
4. **运行时**，遵循 `.agents/MEMORY/memorys/` 中的既有记忆，并将新发现写入其中。
5. **结束时**，将临时产物放入 `tmps/`，将值得保留的知识存入 `memorys/`。

> `.agents/` 中除 `memorys/` 和 `tmps/` 外均为静态规则文件，由项目维护者更新。
> 静态规则通过 agent_kit 统一同步；直接修改会在下次 `agent-kit update` 时被覆盖。
