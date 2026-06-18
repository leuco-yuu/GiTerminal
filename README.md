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

## v0.4.3 界面修复与 Git 功能补强

- 去除原生 QMenuBar 占位空行，顶部只保留模板内菜单栏。
- 底部栏删除无效标签页，只保留终端输出与底部输入框。
- 恢复左侧栏、右侧栏、底部终端的展开/折叠按钮。
- 左侧 Activity Bar 全部改为自绘 SVG 图标，并仅作为布局/导航入口，避免和工作区标签重复。
- 工作区入口点击会切换到工作区并刷新状态。
- 分支有向图改为主题一致背景、S 形曲线边、parent -> child 箭头方向、分支标签指向节点、节点仍保持日期短标签。
- 顶部模板菜单补充标签/Stash、平台、视图、高级操作，并新增 cherry-pick、revert、reset --hard、worktree、submodule、LFS 等入口。

## v0.5.3 更新

- 所有输入提示重新改为覆盖中央工作区域，不再覆盖底部终端。
- 工作区覆盖层固定显示：左上角“← 返回”、底部“取消 / 确定”。
- 新增通用 `request_workspace_form()`，支持一次展示多个输入框。
- Clone、创建 GitHub 仓库、Push -u、Worktree Add、Submodule Add、Add Remote、Set Remote URL、Delete Remote Branch、创建 Tag 等多参数操作改为一次性填写，不再分步弹出。
- 保留单字段操作的兼容入口 `request_terminal_text()`，内部也统一走工作区覆盖层。

## v0.7.0 更新

- 深度精简顶部菜单和右侧 ACTIONS 栏，删除重复、低频、容易造成视觉拥挤的入口。
- 保留高频操作：打开/克隆/初始化、add、commit、diff、分支、fetch/pull/push、tag/stash、平台账户。
- 高级/低频功能统一保留在“全部 Git 命令”、Object Inspector 和 Raw Terminal 中，不再重复堆在右侧栏。
- 右侧栏按钮分组更短，视觉负担更低；完整 Git 能力仍通过高级命令入口兜底。

## v0.8.0 优化项

- GitHub / GitLab / Gitee 支持多账号 SSH Host alias 配置：一键生成 ed25519 key、写入 `~/.ssh/config`、尝试 `ssh-add`、输出公钥并执行 `ssh -T` 测试。
- 支持 HTTPS remote 配置：设置 `credential.helper`、更新当前仓库 remote URL，并自动执行 `git ls-remote` 测试。
- GitHub / GitLab 新增一键安装 `gh` / `glab`，安装流程结束后跳转到新的 `GitHub CLI` / `GitLab CLI` 页面。
- `GitHub CLI` / `GitLab CLI` 页面提供 repo clone/create、PR/MR create/checkout、Issue create/list、Release、Actions/Pipeline 等常用交互式入口。
- 所有工作区表单中的目录类字段新增 📁 文件夹按钮；clone 父目录、CLI clone 父目录、worktree/submodule 父目录不存在时会自动创建。
- 输入框改为内容优先的紧凑宽度，表单标签右对齐，避免输入框横向撑满页面。
- Diff 标签页改为折叠树：文件 -> file/header -> hunk -> 具体变更行，并对新增、删除、hunk、元信息进行颜色高亮。
- 有向图普通滚轮不再滚动画布，仅保留 Ctrl+滚轮缩放；右侧信息树保留独立纵向/横向滚动条。
- 有向图右键菜单新增“Create tag here”，会拒绝创建已有标签。
- 右侧 ACTIONS 分组可折叠，末尾新增 Custom 分组；用户可以新增/删除自定义按钮。
- 暴露 `MainWindow.register_custom_button(name, commands, persist=True)` 接口，`commands` 支持一行或多行 shell/git 指令。

## v0.8.2 Windows CLI install fallback

- Windows 上安装 `gh` / `glab` 时，优先使用已存在的 `winget` / `choco` / `scoop`。
- 如果没有任何包管理器，自动从官方 latest release 下载 Windows zip，解压到 `%LOCALAPPDATA%\\GitTerminal\\bin`，并写入当前用户 PATH。
- 安装后必须执行 `gh --version` / `glab --version` 成功才会进入对应 CLI 页面；失败时保留错误输出，不再提示“流程结束”。

## v0.8.3 Remote / Config UI polish

- 修正工作区覆盖表单的标签列和输入列：同一表单内所有输入框左边界、右边界统一对齐，标签右对齐并与控件垂直居中。
- Clone / Remote 等弹窗中的 URL、父目录字段统一宽度；文件夹选择按钮继续嵌入在输入框尾部，不再额外占列。
- URL 字段不再因为标签包含“远程”而错误显示 remote 名称下拉建议。
- 新增“平台 -> Git 配置”页面：支持读取、设置、删除、列出 `git config` 的 global/local/system 配置，覆盖 `http.proxy`、`https.proxy`、`credential.helper`、`core.sshCommand`、`pull.*`、`core.*` 等常用项。
- 新增 SSH Host / 端口配置入口：写入 `~/.ssh/config` 的 Host、HostName、Port、User、IdentityFile；同时保留 `core.sshCommand` 配置入口。
- 合并 GitHub 与 GitHub CLI、GitLab 与 GitLab CLI 标签页，避免重复页面；安装成功后跳转到合并后的 GitHub / GitLab 页。
- 远程页新增 Set Tracking、Push -u、SSH Auth、HTTPS Auth、Test Auth 入口，不要求先登录 GitHub/GitLab 才能配置 Git remote 认证。
- Custom 按钮的 commands 输入改为多行输入框，真正支持一行或多行 shell/git 指令。
- 替换应用图标为简洁单色风格 SVG。

## v0.8.4 Bottom status strip

- 新增 VS Code 风格底部状态行，原本显示在工作区顶部的仓库、分支、HEAD、远程、Upstream、Ahead/Behind、Dirty、Mode 等信息已全部移到底部。
- 底部状态行增加更细的状态拆分：暂存数量、工作区修改数量、未跟踪数量、冲突数量、Push 目标、Local 路径、Git 版本。
- Push URL、Local 路径、仓库路径等长文本会在状态行中缩短显示，完整信息保留在 tooltip 中；HTTPS URL 中的明文凭据会在状态行中脱敏。

## v0.8.6 Status / Config / CLI fixes

- 底部状态行不再使用主题强调色：深色模式使用深灰，浅色模式使用浅灰。
- Git config 列表支持直接双击编辑 Key / Value；修改后自动执行对应 `git config --<scope>`，失败时回滚界面。
- 修复 Custom 按钮点击时 PyQt `clicked(bool)` 覆盖命令字符串导致的闪退。
- Windows 无包管理器安装 `gh` / `glab` 时，不再使用超长 `PowerShell -EncodedCommand`；改为写入临时 `.ps1` 后通过 `powershell.exe -File` 执行，避免 `命令行太长`。

## v0.8.7 Proxy clear behavior

- Git 代理配置不再把“key 不存在”误判为失败：清空 `http.proxy` / `https.proxy` / `http.noProxy` 时会先检测是否存在。
- 不存在的代理项会显示“未配置，无需删除”，存在的项才执行 `git config --unset-all`。
- 代理设置/清空流程改为逐项执行，最后单独列出当前作用域的 Git config，避免无害返回码污染整个操作结果。

## v0.8.8 Remote tracking panel

- 远程页顶部新增固定的 `Tracking / Upstream` 面板，不再把跟踪分支入口藏在按钮网格或滚动区域里。
- 新增独立按钮：`Track existing remote branch` 和 `Publish local branch + track (Push -u)`。
- 当远程分支不存在时，`Track existing` 会提示改用 `Push -u`，并可直接确认执行 `git push -u <remote> <local-branch>`。
- 右侧 ACTIONS > Remote 也新增 `Track Existing` 和 `Push -u` 快捷入口。
