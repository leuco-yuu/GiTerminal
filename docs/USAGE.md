# 使用指南

本文档说明 Git Terminal 的常用操作方式。项目底层仍然使用本机 Git CLI，因此所有操作都应符合 Git 原生命令语义。

## 启动

源码运行：

```bash
python run.py
```

安装后运行：

```bash
git-terminal
```

启动后应用会尝试检测：

- Git 版本。
- Git 用户配置。
- 默认分支配置。
- credential helper。
- SSH 可用性。
- GitHub CLI / GitLab CLI 等平台工具。

## 打开或创建仓库

常见入口：

- 打开本地仓库。
- 初始化当前目录或指定目录。
- 克隆远程仓库。

如果打开的目录不是 Git 仓库，应用会引导执行 `git init`。

## 工作区操作

工作区通常分为三类：

- Changed：已跟踪文件的修改。
- Staged：已暂存文件。
- Untracked：未跟踪文件。

常用操作：

```text
Stage selected      暂存选中文件
Stage all           暂存全部更改
Unstage selected    取消暂存选中文件
Unstage all         取消暂存全部文件
Restore selected    恢复选中文件
Clean               清理未跟踪文件
```

`Clean` 属于高风险操作，执行前应确认不会删除需要保留的文件。

## 查看差异

常用入口：

- `git diff`：查看工作区和索引差异。
- `git diff --staged`：查看暂存区和 HEAD 差异。

Raw Terminal 示例：

```bash
:git diff --stat
:git diff --name-only
:git diff --staged
```

## 提交

普通提交：

```bash
:git commit -m "message"
```

界面也提供提交表单入口。提交前建议确认：

```bash
:git status -sb
:git diff --staged
```

amend 提交入口会调用类似：

```bash
:git commit --amend --no-edit
```

amend 会改写最后一次提交对象，推送后再 amend 可能影响协作分支。

## 历史和提交图

历史页会展示 commit graph 和 commit 详情。常用能力：

- 单击 commit 查看详情。
- 右键 commit 执行 checkout、branch、cherry-pick、revert、reset hard 等操作。
- 复制 commit hash。
- 查看对象类型或对象内容。

Raw Terminal 示例：

```bash
:git log --oneline --graph --decorate --all
:git show --stat --patch --pretty=fuller HEAD
:git cat-file -t HEAD
:git cat-file -p HEAD^{tree}
```

## 分支

常用操作：

```bash
:git branch -a -vv
:git switch <branch>
:git switch -c <new-branch>
:git merge <branch>
:git rebase <branch>
:git branch -d <branch>
```

删除分支、reset hard、rebase 等操作需要确认当前分支状态和远程同步状态。

## 远程仓库

常用命令：

```bash
:git remote -v
:git remote add origin <url>
:git remote set-url origin <url>
:git fetch --all --prune
:git push -u origin <branch>
:git pull --ff-only
```

删除远程分支示例：

```bash
:git push origin --delete <branch>
```

删除远程分支属于高风险操作。

## Tag

常用命令：

```bash
:git tag --list
:git tag -a v1.0.0 -m "v1.0.0"
:git push origin v1.0.0
:git push origin --tags
:git tag -d v1.0.0
```

删除或覆盖 tag 可能影响发布流程，应谨慎操作。

## Stash

常用命令：

```bash
:git stash list
:git stash push -u -m "work in progress"
:git stash apply stash@{0}
:git stash pop stash@{0}
:git stash drop stash@{0}
:git stash clear
```

`stash clear` 会清除全部 stash，执行前应确认没有重要临时修改。

## 冲突处理

发生 merge/rebase/cherry-pick 冲突后，可使用冲突面板执行：

- use ours。
- use theirs。
- mark resolved。
- continue。
- abort。
- skip。

建议处理流程：

```bash
:git status -sb
# 手动查看冲突文件
:git diff
# 解决冲突后
:git add <file>
:git status -sb
```

再执行 continue。

## 平台相关能力

GitHub / GitLab / Gitee 页面属于平台增强能力。常见前置条件：

```bash
gh auth status
glab auth status
ssh -T git@github.com
ssh -T git@gitlab.com
```

HTTPS remote 和 SSH remote 的认证机制由 Git、平台 CLI、credential helper 或系统凭据管理器承担。

## Raw Terminal 输入规则

底部命令栏可输入 Git 或 shell 命令。以 `:git` 开头时通常表示执行 Git 命令，例如：

```bash
:git status -sb
```

执行高风险 Git 命令时，应用会触发确认流程。

## 推荐工作流

### 新仓库初始化

```bash
:git init
:git config user.name "Your Name"
:git config user.email "you@example.com"
:git add -A
:git commit -m "initial commit"
```

### 新功能分支

```bash
:git switch -c feature/name
# edit files
:git status -sb
:git add -A
:git commit -m "feat: describe change"
:git push -u origin feature/name
```

### 同步远程

```bash
:git fetch --all --prune
:git status -sb
:git pull --ff-only
```

## 注意事项

- 高风险确认不能替代备份策略。
- 对协作分支执行 force push 前，应确认团队约定。
- 对大仓库执行 `git log --all`、`git fsck`、`git gc` 等命令可能耗时较长。
- 平台 token 不应硬编码在项目文件中。
