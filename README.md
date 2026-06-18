# Git Terminal

**Git Terminal** 是一个使用 **PyQt6** 实现的 Git 管理终端。它遵循“本地 Git CLI 为核心、命令透明、安全确认、常用功能图形化、高级功能参数化”的设计方式。

> 重要：本项目不重新实现 Git。所有 Git 操作都通过本机 `git` 可执行文件完成；界面会在执行前展示真实命令，在执行后记录输出。

## 功能概览

### 1. 环境检测

启动后自动检测：

- `git --version`
- `user.name`
- `user.email`
- `init.defaultBranch`
- `credential.helper`
- `ssh`
- GitHub CLI `gh`

### 2. 仓库生命周期

- 打开本地仓库
- 非 Git 目录引导 `git init`
- 初始化仓库
- 克隆远程仓库
- 顶部展示仓库、分支、HEAD、upstream、ahead/behind、dirty、Git 状态机模式

### 3. 工作区 / 暂存区 / 提交

- `git status --porcelain`
- Changed / Staged / Untracked 三栏视图
- Stage selected / Stage all
- Unstage selected / Unstage all
- Restore selected
- Clean untracked，高风险二次确认
- `git diff`
- `git diff --staged`
- `git commit -m`
- `git commit --amend --no-edit`

### 4. 提交历史和提交图

- `git log --graph --decorate --all`
- 提交 graph 文本视图
- commit 单击详情
- `git show --stat --patch --pretty=fuller`
- 右键 commit：checkout、create branch、cherry-pick、revert、reset hard、diff、copy hash、cat-file

### 5. 分支

- `git branch -a -vv`
- 创建分支
- 切换分支
- 删除分支
- merge into current
- rebase onto branch
- push -u
- branch 右键菜单

### 6. Remote

- `git remote -v`
- add / remove / set-url
- fetch
- fetch --all --prune
- push
- delete remote branch，高风险二次确认

### 7. Tag / Stash

- tag list / create annotated tag / delete / push / push --tags
- stash list / push -u / apply / pop / drop / clear

### 8. 冲突解决

- 识别 `UU` / `AA` / `DU` / `UD` 等冲突状态
- use ours
- use theirs
- mark resolved
- merge/rebase/cherry-pick continue / abort / skip

### 9. 专家模式

包含常用底层对象和维护命令：

- `git cat-file`
- `git hash-object`
- `git ls-tree`
- `git ls-files`
- `git rev-parse`
- `git show-ref`
- `git for-each-ref`
- `git write-tree`
- `git commit-tree`
- `git count-objects`
- `git fsck`
- `git gc`
- `git reflog`
- `git archive`
- `git bundle`
- `git maintenance`
- `git submodule`
- `git lfs`
- `git config`

### 10. 全部 Git 命令覆盖

“全部命令”面板采用两种方式覆盖完整 Git 命令能力：

1. 内置完整常用命令目录，包括 porcelain、remote、config、email、plumbing、maintenance、extension 等分类。
2. 启动时调用本机 `git help -a`，动态发现当前 Git 版本支持的全部命令和扩展命令。

因此，新版本 Git 或本地安装的扩展命令也能显示在高级参数面板中。任何命令都可以通过：

- 命令下拉框
- 常用选项 checkbox
- 参数输入框
- 底部 Raw Git Terminal

执行。

### 11. 平台增强

平台页提供增强入口：

- `gh auth status`
- `gh repo list`
- `gh pr list`
- `gh issue list`
- `gh release list`
- `glab auth status`
- `glab mr list`
- `glab issue list`
- Gitee token 查询仓库示例

生产环境中 token 应接入系统 Keychain、Windows Credential Manager 或 Linux Secret Service。

## 安装与运行

```bash
cd git_terminal_project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python run.py
```

## 安全策略

以下命令会触发高风险确认，需要输入确认词：

- `git reset --hard`
- `git clean -f/-fd`
- `git branch -D`
- `git push --force`
- `git push --force-with-lease`
- `git push --delete`
- `git update-ref`
- `git filter-branch`
- `git filter-repo`
- `git tag -f/-d`
- `git reflog expire`
- `git prune`
- `git gc --prune=now`

## 项目结构

```text
git_terminal_project/
  run.py
  requirements.txt
  README.md
  git_terminal/
    app.py
    core/
      commands.py        # Git 命令目录 + git help -a 动态发现
      models.py          # 数据模型
      runner.py          # 本机 git CLI runner
      safety.py          # 风险识别和确认词
    ui/
      main_window.py     # PyQt 主界面
      workers.py         # 后台命令线程
  tests/
    test_safety.py
```

## 设计取舍

- UI 常用功能已经实现为按钮、列表、右键菜单。
- 所有 Git 命令通过“全部命令”面板和 Raw Git Terminal 兜底。
- PR / Issue / Release / CI 属于平台 API 能力，本版本提供 CLI/API 扩展入口，不把平台能力伪装成 Git 命令。
- 大仓库场景建议继续增加分页加载、虚拟列表和缓存层。

## 常见命令示例

底部命令栏可直接输入：

```bash
:git status -sb
:git log --oneline --graph --decorate --all
:git cat-file -p HEAD^{tree}
:git fsck --full
:git update-ref refs/heads/test <hash>
```

高风险命令执行前会弹出二次确认。

## v0.5.6 更新

- “缩小终端”现在固定恢复到初始底部终端高度，不再恢复到拖拽前的任意高度。
- 新增明显的仓库目标信息栏，展示当前提交/分支会推送到哪个 upstream、Push URL 和本地路径。
- 顶部状态栏中文化并强化基础参数：仓库、分支、HEAD、远程、Upstream、Ahead/Behind、Dirty、Mode。
- 新增 `RepoTargetLabel` 样式，提交目标信息在深色/浅色主题下都明显可读。

## v0.5.7 更新

- 修复创建新分支等输入确认后，如果回调内部异常会导致窗口闪退的问题：工作区表单回调和 Git 命令完成回调都加了异常保护，错误进入底部日志。
- 新增 `tests/test_runner_workflows.py`，覆盖真实 Git 仓库中的 init/config/add/commit/branch/switch/merge/tag/stash/remote/push/worktree/object/count-objects/fsck 等流程。
- 保留无效工作目录测试，确认 Windows `WinError 267` 类问题不会再直接抛出到 UI 线程。
- 当前测试数从 4 个扩展到 6 个。

## v0.5.8 更新

- 初始界面高度继续收窄为 1040×620。
- 终端输入行移动到终端顶部固定显示，避免全屏时被 Windows 任务栏遮挡。
- 终端拖拽只会增大终端区域，不再因为轻微向上拖动自动进入全局终端；全局终端仅通过“放大/缩小终端”按钮或菜单进入。
- 中央工作区设置最小高度，防止拖动终端时把工作区完全挤没。
- 有向图刷新时保留当前缩放、视图中心和选中节点；节点操作后不会强制 fit 到全局视角。
- 终端输入行增加状态底色：运行中蓝色、成功绿色、失败红色、警告黄色。

## v0.5.9 更新

- 新增“打开仓库文件夹”入口：顶部文件菜单、右侧上下文操作区、工作区按钮区都可以直接打开当前仓库目录。
- 将 `Stage All` 明确改为 `git add -A / 添加全部`，避免误以为只添加当前选中文件。
- 提交流程改为 `Add All + Commit...`：默认先执行 `git add -A`，把新增、修改、删除的文件全部加入暂存区，再执行 `git commit -m`。
- `Add All + Commit...` 表单支持输入 `no`，用于只提交已经暂存的内容。
- `git add -A` 失败时会停止 commit 并把错误写入终端日志，不再继续提交或闪退。
- 新增多未跟踪文件测试，覆盖包含中文路径、空格文件名、多文件的 `git add -A` + commit 流程。
- 继续保留工作区表单回调和命令完成回调异常保护，commit 后刷新异常不会导致窗口直接崩溃。

## v0.6.0 更新

- 全局补齐静态文本主题适配：`QLabel`、`QGroupBox`、`QCheckBox`、`QComboBox`、`QLineEdit`、`QTextEdit`、Header、滚动区等控件都会随深色/浅色主题切换文字、背景和边框颜色。
- 调整按钮尺寸策略：普通按钮限制最大宽度，避免被布局过度横向拉伸；各功能区按钮网格从过密列数收敛为更松散的 3 列布局，减少高级页面按钮重叠/挤压。
- 工作区页面统一放入可滚动容器。拖动终端边界扩大终端时，工作区内容不会被压缩变形，被遮挡或变窄的内容可通过滚动查看。
- 左侧栏新增 `Recent Repositories` 区域，展示最近打开的本地仓库；路径保存到 `~/.git_terminal/config.json`，点击即可重新打开。
- 打开、初始化、clone 成功后会自动记录最近仓库，并刷新左侧导航。
- 平台页面重构为标签页：`GitHub`、`GitLab`、`Gitee`、`高级配置`。分别提供认证初始化、仓库列表、PR/MR、Issue、Release、CI、Remote 检查、SSH/credential 等入口。

## v0.6.1 更新

- 左侧栏和右侧栏取消最小宽度限制：`SidePanel`、标题栏、标题文本、头部按钮、导航树都允许被 splitter 压缩到接近 0。
- 左侧导航树启用横向滚动条，不再因为仓库路径或长文本强制撑宽侧栏；侧栏变窄后可横向滚动查看完整文本。
- 调整侧栏标题和头部按钮尺寸策略，避免折叠按钮、刷新按钮等固定尺寸控件继续限制侧栏最短宽度。
- 工作区按钮进一步压缩：普通按钮限制最大宽度，降低最小宽度和高度，避免按钮在网格中横向铺满导致界面拥挤。
- 工作区 changed/staged/untracked 区块允许收缩，内部内容通过滚动查看，避免整体布局被列表最小宽度撑爆。
- 视觉样式继续收敛：按钮、GroupBox、滚动区边框更轻，减少大块深色按钮造成的压迫感。

## v0.6.2 更新

- 中央工作区不再展示操作按钮：工作区内保留列表、文本框、输出框、静态提示和表单字段，操作入口统一移动到右侧 ACTIONS 栏。
- 右侧 ACTIONS 栏重构为可滚动操作面板，按 Repository / Changes / History / Branch / Remote / Tags / Advanced / Platform 分组。
- 右侧操作按钮按宽度分布：短按钮一行两个，长按钮一行一个。
- 右侧栏加入滚动容器，操作项较多时通过滚轮访问，不再挤压中央工作区。
- 全局滚动条宽度从 12px 收窄为 8px，水平/垂直滚动条都更轻。
- 中央工作区隐藏原按钮后，所有核心功能仍保留在右侧操作栏和顶部菜单中。
