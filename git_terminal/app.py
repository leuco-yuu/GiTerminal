import sys
from PyQt6.QtCore import qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
from git_terminal.ui.main_window import MainWindow


def _qt_message_handler(_mode, _context, message: str) -> None:
    # Some Qt/font backends emit this harmless warning on Windows/Anaconda
    # during font fallback. Do not let it pollute the terminal output.
    if "QFont::setPointSize: Point size <= 0" in message:
        return
    print(message, file=sys.stderr)


def main() -> int:
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    app.setApplicationName("Git Terminal")
    app.setOrganizationName("Git Terminal")
    win = MainWindow()
    win.show()
    return app.exec()
