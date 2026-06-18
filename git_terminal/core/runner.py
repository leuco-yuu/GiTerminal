from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

from git_terminal.core.models import GitResult, GitStatusItem, RepositorySummary
from git_terminal.core.encoding import completed_process_text, timeout_output_text, utf8_subprocess_env


class GitRunner:
    """Thin wrapper around the system git CLI.

    Git Terminal intentionally does not reimplement Git. It executes the local
    `git` binary, records commands, and exposes raw command escape hatches.
    """

    def __init__(self, repo_path: Optional[str | Path] = None) -> None:
        self.repo_path: Optional[Path] = Path(repo_path).resolve() if repo_path else None
        self.git_executable = shutil.which("git") or "git"

    def set_repo(self, path: str | Path) -> None:
        self.repo_path = Path(path).resolve()

    def cwd(self, override: Optional[str | Path] = None) -> Optional[str]:
        path = Path(override).resolve() if override else self.repo_path
        if path is None:
            return None
        return str(path)

    def run(self, args: Iterable[str], cwd: Optional[str | Path] = None, timeout: int = 120) -> GitResult:
        arg_list = [str(a) for a in args if str(a) != ""]
        if arg_list and arg_list[0] == "git":
            cmd = arg_list
        else:
            cmd = [self.git_executable] + arg_list
        env = utf8_subprocess_env()
        env.setdefault("GIT_PAGER", "cat")
        env.setdefault("PAGER", "cat")
        # Prevent invisible terminal credential prompts from freezing the UI.
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.cwd(cwd),
                text=False,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
            stdout, stderr = completed_process_text(proc)
            return GitResult(cmd, self.cwd(cwd), proc.returncode, stdout, stderr)
        except FileNotFoundError as exc:
            return GitResult(cmd, self.cwd(cwd), 127, "", str(exc))
        except NotADirectoryError as exc:
            return GitResult(cmd, self.cwd(cwd), 1, "", f"Invalid working directory: {self.cwd(cwd)}\n{exc}")
        except OSError as exc:
            return GitResult(cmd, self.cwd(cwd), 1, "", f"OS error while running command in {self.cwd(cwd)}: {exc}")
        except subprocess.TimeoutExpired as exc:
            return GitResult(cmd, self.cwd(cwd), 124, exc.stdout or "", (exc.stderr or "") + "\nCommand timed out")

    def run_raw(self, raw_command: str, cwd: Optional[str | Path] = None, timeout: int = 120) -> GitResult:
        raw_command = raw_command.strip()
        if raw_command.startswith(":"):
            raw_command = raw_command[1:].strip()
        parts = shlex.split(raw_command)
        if parts and parts[0] == "git":
            parts = parts[1:]
        return self.run(parts, cwd=cwd, timeout=timeout)

    def detect_git(self) -> GitResult:
        return self.run(["--version"], cwd=None)

    def parse_status(self) -> List[GitStatusItem]:
        result = self.run(["status", "--porcelain=v1", "--untracked-files=all"])
        items: List[GitStatusItem] = []
        if not result.ok:
            return items
        for line in result.stdout.splitlines():
            if not line:
                continue
            if len(line) < 4:
                continue
            index_status = line[0]
            worktree_status = line[1]
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            items.append(GitStatusItem(path=path, index_status=index_status, worktree_status=worktree_status))
        return items

    def summarize(self) -> RepositorySummary:
        summary = RepositorySummary(path=self.repo_path)
        if not self.repo_path:
            return summary
        summary.name = self.repo_path.name

        branch = self.run(["branch", "--show-current"])
        if branch.ok and branch.stdout.strip():
            summary.branch = branch.stdout.strip()
        else:
            detached = self.run(["rev-parse", "--short", "HEAD"])
            summary.branch = "DETACHED" if detached.ok else "-"

        head = self.run(["rev-parse", "--short", "HEAD"])
        if head.ok:
            summary.head = head.stdout.strip()

        upstream = self.run(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        if upstream.ok:
            summary.upstream = upstream.stdout.strip()
            counts = self.run(["rev-list", "--left-right", "--count", "HEAD...@{u}"])
            if counts.ok:
                parts = counts.stdout.split()
                if len(parts) >= 2:
                    summary.ahead = int(parts[0])
                    summary.behind = int(parts[1])

        items = self.parse_status()
        summary.dirty = len(items)
        summary.mode = self.detect_mode()
        remotes = self.run(["remote"])
        if remotes.ok:
            summary.remotes = [x for x in remotes.stdout.splitlines() if x.strip()]
        return summary

    def detect_mode(self) -> str:
        if not self.repo_path:
            return "no-repo"
        git_dir = self.run(["rev-parse", "--git-dir"])
        if not git_dir.ok:
            return "not-a-repo"
        git_dir_path = git_dir.stdout.strip()
        if not os.path.isabs(git_dir_path):
            git_dir_path = str(self.repo_path / git_dir_path)
        markers = {
            "MERGE_HEAD": "MERGING",
            "CHERRY_PICK_HEAD": "CHERRY-PICKING",
            "REVERT_HEAD": "REVERTING",
            "BISECT_LOG": "BISECTING",
        }
        for filename, mode in markers.items():
            if Path(git_dir_path, filename).exists():
                return mode
        if Path(git_dir_path, "rebase-merge").exists() or Path(git_dir_path, "rebase-apply").exists():
            return "REBASING"
        return "normal"
