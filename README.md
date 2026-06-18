# Git Terminal

Git Terminal 是一个基于 **PyQt6** 的桌面 Git 管理终端。项目定位不是重新实现 Git，而是围绕本机 `git` CLI 构建一个可视化、命令透明、带高风险确认机制的 Git 操作界面。

界面执行的核心操作最终都会落到本机 Git 可执行文件；用户可以在执行前看到真实命令，在执行后查看 stdout/stderr 输出。这使项目同时保留 Git 原生命令能力和桌面 GUI 的易用性。

## 主要特性

### 本机 Git CLI 驱动

- 通过本机 `git` 执行所有 Git 操作。
- 不隐藏命令细节，便于审计、复现和排错。
- 支持底部 Raw Git Terminal 直接输入原生命令。
- 启动时可检测 Git、SSH、GitHub CLI 等环境能力。

### 仓库生命周期管理

- 打开本地仓库。
- 初始化非 Git 目录。
- 克隆远程仓库。
- 展示当前仓库、分支、HEAD、upstream、ahead/behind、dirty 状态和 Git 状态机模式。

### 工作区、暂存区和提交

- `git status --porcelain` 状态解析。
- Changed / Staged / Untracked 三栏工作区视图。
- Stage selected、Stage all、Unstage selected、Unstage all。
- Restore selected、Clean untracked。
- `git diff`、`git diff --staged`。
- 普通提交与 amend 提交入口。

### 历史、提交图和对象检查

- `git log --graph --decorate --all` 文本视图。
- 图形化提交关系视图。
- commit 详情、stat、patch、fuller 信息。
- commit 右键操作：checkout、create branch、cherry-pick、revert、reset hard、diff、copy hash、cat-file。

### 分支、远程、Tag、Stash

- 分支列表、创建、切换、删除、合并、rebase、push -u。
- remote list/add/remove/set-url/fetch/fetch all prune/push。
- tag list/create annotated/delete/push/push --tags。
- stash list/push -u/apply/pop/drop/clear。

### 冲突处理

- 识别常见冲突状态：`UU`、`AA`、`DU`、`UD` 等。
- use ours、use theirs、mark resolved。
- merge/rebase/cherry-pick continue、abort、skip。

### 高级命令覆盖

项目内置常用 Git 命令目录，并在运行时通过 `git help -a` 动态发现当前 Git 版本支持的命令和扩展命令。高级面板支持：

- porcelain 命令。
- remote/config/email/plumbing/maintenance/extension 等分类。
- 常用选项 checkbox。
- 自定义参数输入。
- Raw Git Terminal 兜底执行。

### 平台增强入口

平台页保留 GitHub、GitLab、Gitee 等平台相关入口，包括账号状态、仓库、PR/MR、Issue、Release、CI/Pipeline 等常用交互。平台能力依赖对应 CLI 或 API，不会被伪装为原生 Git 命令。

## 安全模型

项目会对高风险 Git 命令进行识别，并在执行前触发确认流程。典型高风险操作包括：

- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git push --force`
- `git push --force-with-lease`
- `git push --delete`
- `git update-ref`
- `git filter-branch`
- `git filter-repo`
- `git tag -f` / `git tag -d`
- `git reflog expire`
- `git prune`
- `git gc --prune=now`

安全识别逻辑位于 `src/git_terminal/core/safety.py`。测试覆盖位于 `tests/test_safety.py`。

## 运行环境

建议环境：

- Python 3.10 或更高版本。
- Git CLI 已安装并可通过 `git --version` 调用。
- 可用的桌面图形环境。
- PyQt6 运行时依赖。

可选工具：

- `ssh`：用于 SSH remote、平台 SSH Key 测试。
- `gh`：GitHub CLI。
- `glab`：GitLab CLI。
- `keyring` 后端：用于凭据相关扩展。

## 快速开始

### 1. 创建虚拟环境

```bash
python -m venv .venv
```

Linux / macOS：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

Windows CMD：

```bat
.venv\Scripts\activate.bat
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

开发环境可安装额外工具：

```bash
pip install -r requirements-dev.txt
```

### 3. 启动应用

源码方式运行：

```bash
python run.py
```

Linux / macOS 也可以运行：

```bash
./run
```

可编辑安装后运行：

```bash
pip install -e .
git-terminal
```

GUI 入口也会注册为：

```bash
git-terminal-gui
```

## 常用命令示例

底部 Raw Git Terminal 可直接输入：

```bash
:git status -sb
:git log --oneline --graph --decorate --all
:git cat-file -p HEAD^{tree}
:git fsck --full
:git update-ref refs/heads/test <hash>
```

高风险命令会在执行前进入确认流程。

## 项目结构

```text
git_terminal_project/
├── src/
│   └── git_terminal/
│       ├── app.py                  # PyQt 应用入口
│       ├── i18n.py                 # 多语言配置与翻译服务
│       ├── language_config.json    # 内置语言资源
│       ├── assets/                 # SVG 图标资源
│       ├── core/
│       │   ├── commands.py         # Git 命令目录和 git help -a 动态发现
│       │   ├── encoding.py         # 跨平台命令输出解码
│       │   ├── models.py           # 数据模型
│       │   ├── runner.py           # 本机 Git CLI runner
│       │   └── safety.py           # 风险识别和确认策略
│       └── ui/
│           ├── main_window.py      # 主窗口和主要交互逻辑
│           ├── workers.py          # 后台命令线程
│           ├── theme.py            # 主题和配色
│           ├── vscode_shell.py     # 类 VS Code Shell 布局组件
│           └── commit_graph.py     # 提交图视图
├── tests/
│   ├── test_runner_workflows.py    # Git runner 工作流测试
│   └── test_safety.py              # 高风险命令分类测试
├── docs/
│   ├── ARCHITECTURE.md             # 架构说明
│   ├── DEVELOPMENT.md              # 开发指南
│   ├── RELEASE.md                  # 发布流程
│   └── USAGE.md                    # 使用指南
├── pyproject.toml                  # 构建、包元数据、pytest 配置
├── requirements.txt                # 运行依赖
├── requirements-dev.txt            # 开发依赖
├── MANIFEST.in                     # 源码包资源清单
├── CHANGELOG.md                    # 版本记录
├── CONTRIBUTING.md                 # 贡献指南
├── SECURITY.md                     # 安全说明
├── LICENSE                         # 当前未指定开源协议的说明
├── run.py                          # 源码运行入口
└── run                             # Unix 风格源码运行入口
```

## 测试

运行全部测试：

```bash
python -m pytest
```

测试当前覆盖：

- 高风险命令分类。
- 无效工作目录容错。
- 初始化、提交、分支、合并、tag、stash、remote、push、worktree、cat-file、fsck 等核心 Git 工作流。
- 多个未跟踪文件 `git add -A` 后提交。

## 构建发布包

安装构建工具：

```bash
pip install -r requirements-dev.txt
```

构建源码包和 wheel：

```bash
python -m build
```

产物会生成在 `dist/` 目录。

发布前建议至少执行：

```bash
python -m pytest
python -m build
```

## 配置文件位置

用户级配置默认写入：

```text
~/.git_terminal/
```

语言配置文件：

```text
~/.git_terminal/language_config.json
```

项目内置语言资源位于：

```text
src/git_terminal/language_config.json
```

## 设计约束

- 不重新实现 Git 数据模型，避免和 Git 原生行为产生偏差。
- 所有核心 Git 操作通过本机 Git CLI 完成。
- UI 提供高频操作入口，高级能力交给“全部 Git 命令”和 Raw Terminal。
- 高风险命令必须经过风险分类和确认流程。
- 平台 API/CLI 能力保持为增强入口，不等同于 Git 原生命令。

## 故障排查

### 启动时报 PyQt6 相关错误

确认依赖已安装：

```bash
pip install -r requirements.txt
```

Linux 桌面环境可能还需要安装系统 Qt/OpenGL/X11/Wayland 相关库，具体包名取决于发行版。

### 提示找不到 git

确认 Git 已安装并加入 PATH：

```bash
git --version
```

### 中文文件名状态显示异常

项目已在 runner 中做 UTF-8 环境处理。仍出现异常时，优先确认终端编码、系统区域设置和 Git 配置：

```bash
git config --global core.quotepath false
```

### GitHub / GitLab 平台操作不可用

确认对应 CLI 已安装并登录：

```bash
gh auth status
glab auth status
```

## 文档

- [使用指南](docs/USAGE.md)
- [架构说明](docs/ARCHITECTURE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [发布流程](docs/RELEASE.md)
- [贡献指南](CONTRIBUTING.md)
- [安全说明](SECURITY.md)
- [更新记录](CHANGELOG.md)

## 许可证

当前仓库尚未声明正式开源许可证。
