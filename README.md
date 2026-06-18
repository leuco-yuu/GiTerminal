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
