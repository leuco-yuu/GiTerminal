from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable, Iterable, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from git_terminal.core.models import GitResult
from git_terminal.core.runner import GitRunner


class GitCommandWorker(QObject):
    finished = pyqtSignal(object, object)  # GitResult, callback

    def __init__(self, runner: GitRunner, args: Iterable[str], callback: Optional[Callable[[GitResult], None]] = None, timeout: int = 120):
        super().__init__()
        self.runner = runner
        self.args = list(args)
        self.callback = callback
        self.timeout = timeout

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.runner.run(self.args, timeout=self.timeout)
        except Exception as exc:
            result = GitResult(["git", *self.args], self.runner.cwd(), 1, "", f"Unhandled worker error: {exc}")
        self.finished.emit(result, self.callback)


class ShellCommandWorker(QObject):
    finished = pyqtSignal(object, object)  # GitResult, callback

    def __init__(self, command: str, cwd: str | None, callback: Optional[Callable[[GitResult], None]] = None, timeout: int = 300):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.callback = callback
        self.timeout = timeout

    @pyqtSlot()
    def run(self) -> None:
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["LC_ALL"] = env.get("LC_ALL", "C.UTF-8")
            env["LANG"] = env.get("LANG", "C.UTF-8")
            env["LESSCHARSET"] = "utf-8"
            if sys.platform.startswith("win"):
                cmd = ["cmd.exe", "/d", "/s", "/c", f"chcp 65001>nul & {self.command}"]
            else:
                cmd = ["/bin/sh", "-lc", self.command]
            proc = subprocess.run(
                cmd,
                cwd=self.cwd or None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
            )
            result = GitResult([self.command], self.cwd, proc.returncode, proc.stdout, proc.stderr)
        except Exception as exc:
            result = GitResult([self.command], self.cwd, 1, "", str(exc))
        self.finished.emit(result, self.callback)
