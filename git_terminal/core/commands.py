from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class GitCommandSpec:
    name: str
    category: str
    description: str = ""
    examples: List[str] = field(default_factory=list)
    common_options: List[str] = field(default_factory=list)


# Broad fallback catalog. The UI also loads `git help -a` when available so new
# Git versions and extensions are still surfaced.
FALLBACK_COMMANDS: Dict[str, List[GitCommandSpec]] = {
    "高频 Porcelain": [
        GitCommandSpec("init", "高频 Porcelain", "创建空 Git 仓库或重新初始化现有仓库", ["git init", "git init --initial-branch=main"], ["--bare", "--initial-branch=main"]),
        GitCommandSpec("clone", "高频 Porcelain", "克隆远程仓库", ["git clone <url>", "git clone --depth 1 <url>"], ["--depth 1", "--recurse-submodules", "--branch"]),
        GitCommandSpec("status", "高频 Porcelain", "显示工作区和暂存区状态", ["git status -sb", "git status --porcelain"], ["-sb", "--porcelain", "--ignored"]),
        GitCommandSpec("add", "高频 Porcelain", "添加文件到暂存区", ["git add .", "git add -p src/app.py"], ["-A", "-p", "--intent-to-add"]),
        GitCommandSpec("restore", "高频 Porcelain", "恢复工作区或暂存区文件", ["git restore file", "git restore --staged file"], ["--staged", "--worktree", "--source"]),
        GitCommandSpec("reset", "高频 Porcelain", "重置索引或移动当前分支", ["git reset HEAD file", "git reset --hard HEAD~1"], ["--soft", "--mixed", "--hard", "--merge", "--keep"]),
        GitCommandSpec("rm", "高频 Porcelain", "从工作区和索引删除文件", ["git rm old.txt", "git rm --cached secret.env"], ["--cached", "-r", "-f"]),
        GitCommandSpec("mv", "高频 Porcelain", "移动或重命名文件", ["git mv old.py new.py"], ["-f", "-k"]),
        GitCommandSpec("diff", "高频 Porcelain", "查看差异", ["git diff", "git diff --staged"], ["--staged", "--stat", "--name-only", "--word-diff"]),
        GitCommandSpec("commit", "高频 Porcelain", "创建提交", ["git commit -m 'message'", "git commit --amend"], ["-m", "--amend", "--no-edit", "--signoff", "--allow-empty"]),
        GitCommandSpec("log", "高频 Porcelain", "查看提交历史", ["git log --oneline --graph --decorate --all"], ["--oneline", "--graph", "--decorate", "--all", "--stat", "-p"]),
        GitCommandSpec("show", "高频 Porcelain", "显示对象或提交详情", ["git show HEAD", "git show --stat <hash>"], ["--stat", "--name-only", "--pretty=fuller"]),
        GitCommandSpec("branch", "高频 Porcelain", "创建、列出、重命名、删除分支", ["git branch -vv", "git branch feature/login"], ["-a", "-vv", "-d", "-D", "-m", "--merged", "--no-merged"]),
        GitCommandSpec("switch", "高频 Porcelain", "切换分支", ["git switch main", "git switch -c feature/x"], ["-c", "-C", "--detach", "--track"]),
        GitCommandSpec("checkout", "高频 Porcelain", "切换分支或检出路径", ["git checkout main", "git checkout -- file"], ["-b", "-B", "--detach", "--"]),
        GitCommandSpec("merge", "高频 Porcelain", "合并分支", ["git merge main", "git merge --abort"], ["--no-ff", "--ff-only", "--squash", "--abort", "--continue"]),
        GitCommandSpec("rebase", "高频 Porcelain", "变基提交", ["git rebase main", "git rebase -i HEAD~3"], ["-i", "--onto", "--continue", "--abort", "--skip", "--rebase-merges"]),
        GitCommandSpec("cherry-pick", "高频 Porcelain", "挑选提交到当前分支", ["git cherry-pick <hash>"], ["--continue", "--abort", "--skip", "-n", "-x"]),
        GitCommandSpec("revert", "高频 Porcelain", "创建反向提交", ["git revert <hash>"], ["--continue", "--abort", "--no-edit", "-n"]),
        GitCommandSpec("tag", "高频 Porcelain", "管理标签", ["git tag v1.0.0", "git tag -a v1.0.0 -m 'release'"], ["-a", "-m", "-d", "-f", "--list", "--sort=-creatordate"]),
        GitCommandSpec("stash", "高频 Porcelain", "暂存未提交修改", ["git stash push -m work", "git stash pop"], ["push", "pop", "apply", "list", "drop", "clear", "-u"]),
        GitCommandSpec("worktree", "高频 Porcelain", "管理多个工作树", ["git worktree list", "git worktree add ../repo-feature feature"], ["list", "add", "remove", "prune", "move"]),
    ],
    "远程与同步": [
        GitCommandSpec("remote", "远程与同步", "管理远程仓库", ["git remote -v", "git remote add origin <url>"], ["-v", "add", "remove", "rename", "set-url", "show", "prune"]),
        GitCommandSpec("fetch", "远程与同步", "从远程下载对象和引用", ["git fetch --all --prune"], ["--all", "--prune", "--tags", "--depth", "--force"]),
        GitCommandSpec("pull", "远程与同步", "fetch 后合并或变基", ["git pull --ff-only", "git pull --rebase"], ["--ff-only", "--rebase", "--autostash", "--tags"]),
        GitCommandSpec("push", "远程与同步", "推送本地引用到远程", ["git push -u origin main", "git push --tags"], ["-u", "--tags", "--delete", "--force-with-lease", "--dry-run"]),
        GitCommandSpec("ls-remote", "远程与同步", "列出远程引用", ["git ls-remote origin"], ["--heads", "--tags", "--refs"]),
        GitCommandSpec("request-pull", "远程与同步", "生成请求拉取摘要", ["git request-pull v1.0 origin main"], []),
        GitCommandSpec("submodule", "远程与同步", "管理子模块", ["git submodule update --init --recursive"], ["add", "status", "init", "update", "sync", "foreach", "--recursive"]),
        GitCommandSpec("bundle", "远程与同步", "创建或读取 bundle 文件", ["git bundle create repo.bundle --all"], ["create", "verify", "list-heads", "unbundle"]),
    ],
    "检查与搜索": [
        GitCommandSpec("grep", "检查与搜索", "在跟踪文件中搜索", ["git grep TODO"], ["-n", "-i", "--cached", "--untracked"]),
        GitCommandSpec("blame", "检查与搜索", "查看逐行最后修改", ["git blame file.py"], ["-L", "-w", "--date=short"]),
        GitCommandSpec("bisect", "检查与搜索", "二分查找引入问题的提交", ["git bisect start", "git bisect good", "git bisect bad"], ["start", "good", "bad", "reset", "run", "skip"]),
        GitCommandSpec("shortlog", "检查与搜索", "按作者汇总提交", ["git shortlog -sn --all"], ["-s", "-n", "-e", "--all"]),
        GitCommandSpec("describe", "检查与搜索", "基于最近标签描述提交", ["git describe --tags --always"], ["--tags", "--always", "--dirty", "--long"]),
        GitCommandSpec("range-diff", "检查与搜索", "比较两组提交序列", ["git range-diff main...feature old...new"], []),
        GitCommandSpec("rerere", "检查与搜索", "复用已记录的冲突解决", ["git rerere status"], ["status", "diff", "forget", "gc"]),
    ],
    "配置与身份": [
        GitCommandSpec("config", "配置与身份", "读取或写入 Git 配置", ["git config --global user.name Alice"], ["--global", "--local", "--system", "--list", "--get", "--unset"]),
        GitCommandSpec("help", "配置与身份", "查看 Git 帮助", ["git help commit", "git help -a"], ["-a", "-g", "--config"]),
        GitCommandSpec("version", "配置与身份", "显示 Git 版本", ["git version"], ["--build-options"]),
        GitCommandSpec("credential", "配置与身份", "读取或写入凭据", ["git credential fill"], ["fill", "approve", "reject"]),
        GitCommandSpec("credential-cache", "配置与身份", "凭据缓存 helper", [], []),
        GitCommandSpec("credential-store", "配置与身份", "凭据存储 helper", [], []),
        GitCommandSpec("var", "配置与身份", "显示 Git 逻辑变量", ["git var GIT_AUTHOR_IDENT"], ["-l"]),
    ],
    "邮件与补丁": [
        GitCommandSpec("format-patch", "邮件与补丁", "生成邮件补丁", ["git format-patch -1 HEAD"], ["-o", "--cover-letter", "--stdout"]),
        GitCommandSpec("am", "邮件与补丁", "应用邮件补丁", ["git am patch.mbox"], ["--continue", "--abort", "--skip", "--3way"]),
        GitCommandSpec("apply", "邮件与补丁", "应用补丁到工作区/索引", ["git apply patch.diff"], ["--check", "--cached", "--3way", "--reject"]),
        GitCommandSpec("send-email", "邮件与补丁", "发送补丁邮件", ["git send-email *.patch"], []),
        GitCommandSpec("mailinfo", "邮件与补丁", "从邮件中提取补丁和作者信息", [], []),
        GitCommandSpec("mailsplit", "邮件与补丁", "拆分 mbox 邮件", [], []),
    ],
    "底层对象 Plumbing": [
        GitCommandSpec("cat-file", "底层对象 Plumbing", "显示对象内容、类型、大小", ["git cat-file -p HEAD^{tree}"], ["-p", "-t", "-s", "--batch", "--batch-check"]),
        GitCommandSpec("hash-object", "底层对象 Plumbing", "计算对象 ID，可写入对象库", ["git hash-object file"], ["-w", "--stdin", "-t"]),
        GitCommandSpec("ls-tree", "底层对象 Plumbing", "列出树对象内容", ["git ls-tree -r HEAD"], ["-r", "-l", "--name-only"]),
        GitCommandSpec("ls-files", "底层对象 Plumbing", "列出索引和工作区文件", ["git ls-files -s"], ["-s", "-u", "-o", "--ignored", "--stage"]),
        GitCommandSpec("rev-parse", "底层对象 Plumbing", "解析修订和路径", ["git rev-parse --show-toplevel"], ["--short", "--verify", "--show-toplevel", "--abbrev-ref"]),
        GitCommandSpec("rev-list", "底层对象 Plumbing", "列出提交对象", ["git rev-list --count HEAD"], ["--count", "--objects", "--all", "--left-right"]),
        GitCommandSpec("show-ref", "底层对象 Plumbing", "列出引用", ["git show-ref --heads --tags"], ["--heads", "--tags", "--verify", "--dereference"]),
        GitCommandSpec("for-each-ref", "底层对象 Plumbing", "格式化遍历引用", ["git for-each-ref --format='%(refname)'"], ["--format", "--sort", "--count"]),
        GitCommandSpec("update-ref", "底层对象 Plumbing", "更新引用", ["git update-ref refs/heads/test <hash>"], ["-d", "--stdin", "--no-deref"]),
        GitCommandSpec("symbolic-ref", "底层对象 Plumbing", "读取或设置符号引用", ["git symbolic-ref HEAD"], ["-q", "--short", "-d"]),
        GitCommandSpec("read-tree", "底层对象 Plumbing", "读取树到索引", [], ["-m", "--reset", "-u"]),
        GitCommandSpec("write-tree", "底层对象 Plumbing", "从索引创建树对象", ["git write-tree"], []),
        GitCommandSpec("commit-tree", "底层对象 Plumbing", "从树对象创建提交", ["git commit-tree <tree> -p <parent>"], ["-p", "-m", "-S"]),
        GitCommandSpec("merge-base", "底层对象 Plumbing", "查找共同祖先", ["git merge-base main feature"], ["--all", "--is-ancestor", "--fork-point"]),
        GitCommandSpec("merge-file", "底层对象 Plumbing", "三方文件合并", [], []),
        GitCommandSpec("merge-index", "底层对象 Plumbing", "对未合并索引运行合并程序", [], []),
        GitCommandSpec("merge-tree", "底层对象 Plumbing", "执行树级合并", [], ["--write-tree"]),
        GitCommandSpec("unpack-file", "底层对象 Plumbing", "临时文件形式创建 blob 内容", [], []),
        GitCommandSpec("unpack-objects", "底层对象 Plumbing", "从 pack 解包对象", [], []),
        GitCommandSpec("pack-objects", "底层对象 Plumbing", "创建 packed archive", [], []),
        GitCommandSpec("index-pack", "底层对象 Plumbing", "为 pack 创建索引", [], []),
        GitCommandSpec("pack-refs", "底层对象 Plumbing", "打包引用", ["git pack-refs --all"], ["--all", "--prune"]),
        GitCommandSpec("mktree", "底层对象 Plumbing", "从文本格式构造树对象", [], []),
        GitCommandSpec("mktag", "底层对象 Plumbing", "创建 tag 对象", [], []),
        GitCommandSpec("replace", "底层对象 Plumbing", "替换对象引用", [], ["-d", "--edit", "--graft"]),
        GitCommandSpec("notes", "底层对象 Plumbing", "管理提交 notes", ["git notes add -m note HEAD"], ["add", "append", "show", "list", "remove"]),
    ],
    "维护与诊断": [
        GitCommandSpec("gc", "维护与诊断", "清理和优化仓库", ["git gc"], ["--aggressive", "--auto", "--prune=now"]),
        GitCommandSpec("fsck", "维护与诊断", "验证对象数据库完整性", ["git fsck --full"], ["--full", "--lost-found", "--unreachable"]),
        GitCommandSpec("count-objects", "维护与诊断", "统计松散对象和 pack 大小", ["git count-objects -vH"], ["-v", "-H"]),
        GitCommandSpec("reflog", "维护与诊断", "查看和管理 reflog", ["git reflog", "git switch -c rescue HEAD@{1}"], ["show", "expire", "delete", "exists"]),
        GitCommandSpec("prune", "维护与诊断", "清理不可达对象", ["git prune --dry-run"], ["--dry-run", "--verbose", "--expire"]),
        GitCommandSpec("archive", "维护与诊断", "从树创建归档", ["git archive --format=zip HEAD -o source.zip"], ["--format=zip", "--format=tar", "-o"]),
        GitCommandSpec("maintenance", "维护与诊断", "运行仓库维护任务", ["git maintenance run"], ["run", "start", "stop", "register", "unregister"]),
        GitCommandSpec("multi-pack-index", "维护与诊断", "维护 multi-pack-index", [], ["write", "verify", "expire", "repack"]),
        GitCommandSpec("commit-graph", "维护与诊断", "写入或验证 commit-graph", [], ["write", "verify"]),
        GitCommandSpec("bugreport", "维护与诊断", "生成 Git bug report 模板", ["git bugreport"], []),
        GitCommandSpec("diagnose", "维护与诊断", "生成诊断归档", ["git diagnose"], []),
    ],
    "扩展与生态": [
        GitCommandSpec("lfs", "扩展与生态", "Git LFS 扩展命令，如果已安装", ["git lfs status", "git lfs track '*.bin'"], ["install", "status", "track", "untrack", "pull", "push", "migrate"]),
        GitCommandSpec("svn", "扩展与生态", "Git-SVN 桥接，如果已安装", [], ["clone", "fetch", "rebase", "dcommit"]),
        GitCommandSpec("p4", "扩展与生态", "Git-P4 桥接，如果已安装", [], ["clone", "sync", "rebase", "submit"]),
        GitCommandSpec("gui", "扩展与生态", "启动 git gui，如果已安装", ["git gui"], []),
        GitCommandSpec("k", "扩展与生态", "启动 gitk，如果已安装", ["gitk --all"], ["--all"]),
    ],
}


def flat_fallback_specs() -> List[GitCommandSpec]:
    result: List[GitCommandSpec] = []
    for specs in FALLBACK_COMMANDS.values():
        result.extend(specs)
    return result


def load_git_help_commands() -> List[str]:
    try:
        proc = subprocess.run(["git", "help", "-a"], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=10)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    names = set()
    for line in proc.stdout.splitlines():
        # Lines in `git help -a` often contain command names in columns.
        for token in re.split(r"\s+", line.strip()):
            if re.match(r"^[a-z][a-z0-9-]+$", token):
                # Filter section headings and words that are not commands.
                if token not in {"available", "git", "commands", "main", "ancillary", "interrogators", "interactors", "low-level", "manipulators", "synching", "repositories", "workspace", "history", "others"}:
                    names.add(token)
    return sorted(names)


def build_command_catalog() -> Dict[str, GitCommandSpec]:
    specs = {spec.name: spec for spec in flat_fallback_specs()}
    for name in load_git_help_commands():
        specs.setdefault(name, GitCommandSpec(name=name, category="Git help -a 动态命令", description="由本机 git help -a 动态发现的命令或扩展"))
    return dict(sorted(specs.items(), key=lambda item: item[0]))
