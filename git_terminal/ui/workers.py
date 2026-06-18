from __future__ import annotations

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
        result = self.runner.run(self.args, timeout=self.timeout)
        self.finished.emit(result, self.callback)
