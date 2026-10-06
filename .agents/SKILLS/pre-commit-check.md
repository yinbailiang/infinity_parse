# SKILL: 代码审查前检查

**触发**：提交代码或用户要求 pre-commit 检查。

## 步骤

1. `uv run ruff check .` — lint 检查
2. `uv run ruff format .` — 格式化（仅检查不写入时，为命令追加 `--check`）
3. **零遮蔽检查** — `src/infinity_parse/` 下不得出现任何 `# type:` 或 `# pyright` 注释
   - Windows: `Select-String -Path src\infinity_parse\**\*.py -Pattern "# type:|# pyright"` 应无匹配
   - Unix: `grep -r "# type:\|# pyright" src/infinity_parse/` 应无输出
4. `uv run pyright` — 类型检查（必须零错误）
5. `uv run pytest --cov=infinity_parse --cov-fail-under=90 -q` — 全量测试
6. `uv run interrogate src/infinity_parse/` — 公开 API docstring 覆盖率检查
7. `uv run python example/example.py` — 运行示例冒烟验证
8. `uv run python example/moe_calc.py` — moe_calc 示例冒烟验证
9. `uv run python example/dice_catgirl.py` — dice_catgirl 示例冒烟验证
10. `uv run python example/simple_kv.py` — simple_kv 示例冒烟验证

> 如有问题，修复后从第 1 步重新全量运行。
