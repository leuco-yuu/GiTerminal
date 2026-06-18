from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Iterable, List

from git_terminal.core.models import RiskLevel


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    title: str
    reason: str
    confirmation_word: str = "RUN"


HIGH_RISK_HINTS = (
    "可能丢弃未提交修改、删除引用、改写历史或影响远程仓库。",
    "执行前建议确认当前分支、查看 reflog，并确保已经 push 或备份重要提交。",
)


def normalize_command(command: Iterable[str] | str) -> List[str]:
    if isinstance(command, str):
        parts = shlex.split(command)
    else:
        parts = list(command)
    if parts and parts[0] == "git":
        parts = parts[1:]
    return parts


def classify_git_command(command: Iterable[str] | str) -> RiskAssessment:
    args = normalize_command(command)
    if not args:
        return RiskAssessment(RiskLevel.LOW, "低风险命令", "空命令不会执行。")

    cmd = args[0]
    flags = set(a for a in args[1:] if a.startswith("-"))
    text = " ".join(args)

    # High risk: destructive local or remote operations.
    if cmd == "reset" and ("--hard" in flags or "--merge" in flags or "--keep" in flags):
        return RiskAssessment(RiskLevel.HIGH, "高风险：重置分支", "reset 可能移动当前分支指针；--hard 会丢弃工作区修改。", "RESET")
    if cmd == "clean" and any(f.startswith("-f") or f == "--force" for f in flags):
        return RiskAssessment(RiskLevel.HIGH, "高风险：清理未跟踪文件", "clean -f/-fd 会删除未跟踪文件或目录。", "CLEAN")
    if cmd == "branch" and ("-D" in args or "--delete" in args and "--force" in args):
        return RiskAssessment(RiskLevel.HIGH, "高风险：强制删除分支", "branch -D 可能删除尚未合并的分支引用。", "DELETE")
    if cmd == "push" and any(x in args for x in ["--force", "-f", "--force-with-lease", "+"]):
        return RiskAssessment(RiskLevel.HIGH, "高风险：强制推送", "force push 会改写远程历史，可能影响协作者。", "PUSH")
    if cmd == "push" and any(x in args for x in ["--delete", ":"]):
        return RiskAssessment(RiskLevel.HIGH, "高风险：删除远程引用", "push --delete 或 refspec 删除会影响远程分支/标签。", "DELETE")
    if cmd in {"update-ref", "symbolic-ref"}:
        return RiskAssessment(RiskLevel.HIGH, "高风险：直接修改引用", f"{cmd} 直接操作 Git 引用，可能造成分支或 HEAD 异常。", "REF")
    if cmd in {"filter-branch", "filter-repo", "replace"}:
        return RiskAssessment(RiskLevel.HIGH, "高风险：改写历史", f"{cmd} 会重写对象或引用历史。", "REWRITE")
    if cmd == "tag" and any(x in args for x in ["-f", "--force", "-d", "--delete"]):
        return RiskAssessment(RiskLevel.HIGH, "高风险：移动或删除标签", "移动已发布标签会影响发布与依赖方。", "TAG")
    if cmd == "reflog" and "expire" in args:
        return RiskAssessment(RiskLevel.HIGH, "高风险：删除恢复线索", "reflog expire 可能移除恢复历史的依据。", "EXPIRE")
    if cmd == "prune" or (cmd == "gc" and "--prune=now" in text):
        return RiskAssessment(RiskLevel.HIGH, "高风险：清理对象", "prune/gc --prune=now 可能清理不可达对象，降低恢复可能。", "PRUNE")

    # Medium risk: history-changing but recoverable operations.
    if cmd in {"commit", "merge", "rebase", "cherry-pick", "revert", "switch", "checkout", "restore", "rm", "mv", "stash", "worktree", "submodule"}:
        return RiskAssessment(RiskLevel.MEDIUM, "中风险 Git 操作", f"{cmd} 会修改工作区、索引、历史或仓库结构。")
    if cmd in {"pull", "fetch", "push", "remote", "branch", "tag", "notes"}:
        return RiskAssessment(RiskLevel.MEDIUM, "中风险 Git 操作", f"{cmd} 可能影响远程同步、引用或元数据。")

    return RiskAssessment(RiskLevel.LOW, "低风险 Git 操作", f"{cmd} 通常是查看、检查或读取类操作。")
