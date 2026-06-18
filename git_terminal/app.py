import sys
from PyQt6.QtWidgets import QApplication
from git_terminal.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Git Terminal")
    app.setOrganizationName("Git Terminal")
    win = MainWindow()
    win.show()
    return app.exec()
