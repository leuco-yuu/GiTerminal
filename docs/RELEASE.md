# 发布流程

本文档给出一个保守的 Python 桌面项目发布流程。实际公开发布前，应先确认许可证、版本号、图标素材权属和平台凭据处理方式。

## 1. 确认版本号

当前包版本定义在：

```text
pyproject.toml
```

源码内也有版本常量：

```text
src/git_terminal/__init__.py
```

发布前应让两者保持一致，避免用户看到的版本和包管理器版本不一致。

## 2. 更新变更记录

编辑：

```text
CHANGELOG.md
```

建议格式：

```markdown
## vX.Y.Z - YYYY-MM-DD

### Added
### Changed
### Fixed
### Security
```

## 3. 运行测试

```bash
python -m pytest
```

## 4. 构建包

```bash
python -m build
```

产物：

```text
dist/*.tar.gz
dist/*.whl
```

## 5. 检查包内容

```bash
python -m zipfile -l dist/*.whl
```

必须包含：

- Python 源码包。
- SVG 图标。
- `language_config.json`。
- metadata。

## 6. 本地安装验证

```bash
python -m venv .venv-release
source .venv-release/bin/activate   # Windows: .venv-release\Scripts\activate
pip install dist/*.whl
git-terminal
```

验证：

- 应用能启动。
- 图标正常显示。
- 可以打开仓库并刷新状态。
- Raw Terminal 可执行 `git status -sb`。
- 高风险命令会触发确认。

## 7. 发布到包索引

发布前先使用 TestPyPI 或内部包仓库验证。

```bash
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
```

正式发布：

```bash
python -m twine upload dist/*
```

## 8. 发布归档

创建 Git tag：

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

如果发布 GitHub Release，建议附上：

- 变更摘要。
- 已知问题。
- 安装方式。
- wheel/sdist 或平台包。

## 9. 许可证检查

当前仓库未指定正式开源许可证。公开发布前应替换 `LICENSE` 文件，并同步更新 `pyproject.toml` 的 license 字段和 classifier。
