# SKILL: 修改核心 API

**触发**：用户要求修改项目核心类或公开函数的 API。

## 约束

1. 尽量避免破坏公开 API；无法避免时保留向后兼容，或提供明确的迁移说明
2. 修改后运行全量类型检查：`uv run pyright`
3. 修改后运行全量测试：`uv run pytest --cov=infinity_parse --cov-fail-under=90 -q`
4. 更新 `src/infinity_parse/__init__.py` 中的 `__all__` 导出
5. 同步更新对应文档与示例
