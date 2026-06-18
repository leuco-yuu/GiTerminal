from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class GitResult:
    command: List[str]
    cwd: Optional[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def command_text(self) -> str:
        return " ".join(self.command)

    @property
    def output(self) -> str:
        out = self.stdout or ""
        err = self.stderr or ""
        if out and err:
            return out.rstrip() + "\n" + err.rstrip()
        return (out or err).rstrip()


@dataclass
class GitStatusItem:
    path: str
    index_status: str
    worktree_status: str

    @property
    def staged(self) -> bool:
        return self.index_status not in (" ", "?")

    @property
    def changed(self) -> bool:
        return self.worktree_status not in (" ", "?")

    @property
    def untracked(self) -> bool:
        return self.index_status == "?" and self.worktree_status == "?"

    @property
    def display(self) -> str:
        return f"{self.index_status}{self.worktree_status}  {self.path}"


@dataclass
class RepositorySummary:
    path: Optional[Path] = None
    name: str = "未打开仓库"
    branch: str = "-"
    head: str = "-"
    upstream: str = "-"
    ahead: int = 0
    behind: int = 0
    dirty: int = 0
    mode: str = "normal"
    remotes: List[str] = field(default_factory=list)
