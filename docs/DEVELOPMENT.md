# 开发指南

本文档面向维护者和贡献者，说明本项目的开发、测试和结构约定。

## 本地开发环境

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
```

启动应用：

```bash
python run.py
```

或：

```bash
git-terminal
```

## 目录约定

项目采用 `src/` 布局：

```text
src/git_terminal/   应用包
tests/              测试
docs/               项目文档
scripts/            辅助脚本
```

采用 `src/` 布局的原因：

- 避免从项目根目录误导入未安装包。
- 更接近发布包的真实导入路径。
- 便于发现缺失的 package data 或安装配置问题。

## 运行测试

```bash
python -m pytest
```

当前测试依赖本机 Git CLI。没有 Git 时，工作流测试会跳过。

## 编码约定

- Python 版本：3.10+。
- 文件编码：UTF-8。
- 命令执行输出优先保持 UTF-8 可读。
- UI 文案新增时应考虑 `i18n.py` 的 key 生成和语言配置。
- 新增资源文件时应确认 `MANIFEST.in` 和 `pyproject.toml` 包含对应文件。

## 风险命令开发规范

新增或调整 Git 命令入口时，需要考虑风险等级：

1. 是否会删除文件或引用。
2. 是否会改写历史。
3. 是否会影响远程仓库。
4. 是否会清理不可恢复对象。
5. 是否会绕过 Git 安全保护。

涉及高风险命令时，应补充或更新：

- `src/git_terminal/core/safety.py`
- `tests/test_safety.py`

典型高风险命令：

```bash
git reset --hard
git clean -fd
git push --force-with-lease
git push origin --delete branch
git update-ref -d refs/heads/name
git reflog expire --expire=now --all
git gc --prune=now
```

## GitRunner 开发规范

`GitRunner` 是项目核心边界之一。调整时应保持：

- 不直接拼接 shell 字符串执行 Git 参数列表。
- 捕获 stdout/stderr/returncode。
- 无效工作目录应返回错误结果，而不是抛出未处理异常。
- 超时和异常应尽量返回可展示的 `GitResult`。

## UI 开发规范

- 长耗时任务不要阻塞 Qt 主线程。
- Git 命令优先通过 worker 执行。
- 业务执行前应经过统一风险分类。
- 表单输入需要给出清晰默认值和说明。
- 高级/低频能力优先放入高级面板或 Raw Terminal，避免主界面堆叠。

## 资源文件

SVG 图标资源位于：

```text
src/git_terminal/assets/
```

语言资源位于：

```text
src/git_terminal/language_config.json
```

打包前可检查 wheel 内容：

```bash
python -m build
python -m zipfile -l dist/*.whl
```

确认其中包含：

- `git_terminal/assets/*.svg`
- `git_terminal/language_config.json`

## 发布前检查清单

```bash
python -m pytest
python -m build
```

手工检查：

- `python run.py` 能启动。
- `pip install -e .` 后 `git-terminal` 能启动。
- 图标资源正常显示。
- 语言切换正常。
- 高风险命令仍触发确认。
- README 和 CHANGELOG 已更新。
- LICENSE 已按实际发布策略确认。

## 本地校验脚本

项目提供一个轻量校验脚本：

```bash
python scripts/check_project.py
```

该脚本会执行：

- `compileall` 语法检查。
- `pytest` 测试。
