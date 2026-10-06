# SKILL: 项目发布

**触发**：发布、release、publish、打版、上线、PyPI、版本号升级。

## 流程概览

```text
更新版本号 → 本地验证 → 提交推送 → 打 Git Tag → 推送 Tag → CI/CD 自动发布
```

推送 `v*` 格式的 tag 后，`.github/workflows/publish.yml` 自动执行：构建产物 → GitHub Release → PyPI 发布。

## 步骤

1. **确认状态**

   ```bash
   uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
   git status
   git branch
   ```

2. **更新版本号** — 编辑 `pyproject.toml` 中的版本字段（如项目在 `src/infinity_parse/__init__.py` 维护 `__version__`，一并更新），遵循 [SemVer](https://semver.org/lang/zh-CN/)：

   | 类型 | 场景 | 示例 |
   | - | - | - |
   | patch | Bug 修复、文档更新 | 1.5.0 → 1.5.1 |
   | minor | 新功能、向后兼容 | 1.5.0 → 1.6.0 |
   | major | 破坏性 API 变更 | 1.5.0 → 2.0.0 |

3. **本地最终验证** — 按 pre-commit-check 技能全量验证：

   ```bash
   uv run pytest --cov=infinity_parse --cov-fail-under=90 -q
   ```

4. **同步工程基准快照**（如项目维护基准文档）— 以本次全量验证输出为准，更新测试数 / 覆盖率 / 版本基准等内容。

5. **提交版本更新**

   ```bash
   git add -A
   git commit -m "chore: bump version to <新版本号>"
   git push
   ```

6. **打 Tag 并推送** — Tag 必须以 `v` 开头，否则不会触发发布流程：

   ```bash
   git tag -a v<新版本号>
   git push origin v<新版本号>
   ```

7. **监控 CI/CD** — 前往 https://github.com/yinbailiang/infinity_parse/actions 查看执行状态。

8. **验证发布**

   ```bash
   uv pip install --index-url https://pypi.org/simple/ infinity_parse==<新版本号>
   ```

## 注意事项

- **禁止手动创建 GitHub Release**（如项目由 CI 自动创建发布）
- PyPI 版本**不可覆盖**，发版前务必确认版本号正确
- CI 失败时先修复问题，再删除错误 tag 重新打：

  ```bash
  git tag -d v<版本号>
  git push --delete origin v<版本号>
  ```
