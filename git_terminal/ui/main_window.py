from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import Qt, QThread, QPoint
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from git_terminal.core.commands import GitCommandSpec, build_command_catalog
from git_terminal.core.models import GitResult, GitStatusItem, RiskLevel
from git_terminal.core.runner import GitRunner
from git_terminal.core.safety import classify_git_command
from git_terminal.ui.workers import GitCommandWorker
from git_terminal.ui.theme import apply_theme
from git_terminal.ui.commit_graph import CommitGraphView, GraphCommit


class CloneDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("git@github.com:org/repo.git 或 https://...")
        self.dest = QLineEdit()
        browse = QPushButton("选择目录")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.dest)
        row.addWidget(browse)
        form.addRow("远程 URL", self.url)
        form.addRow("目标目录", row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 clone 到的父目录")
        if directory:
            self.dest.setText(directory)


class RemoteDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.url = QLineEdit()
        form.addRow("remote 名称", self.name)
        form.addRow("URL", self.url)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Git Terminal")
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "git_terminal_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1500, 930)
        self.runner = GitRunner()
        self.command_catalog = build_command_catalog()
        self._threads: List[Tuple[QThread, GitCommandWorker]] = []
        self._option_checks: List[QCheckBox] = []
        self._suppress_preview = False
        self.theme_mode = "dark"
        self.theme_accent = "blue"
        self._left_collapsed = False
        self._right_collapsed = False
        self._bottom_collapsed = False
        self._last_left_width = 240
        self._last_right_width = 300
        self._last_bottom_height = 220

        self._build_actions()
        self._build_ui()
        self._wire_shortcuts()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)
        self.detect_environment()
        self.refresh_all()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        self.open_repo_action = QAction("打开仓库", self)
        self.open_repo_action.triggered.connect(self.open_repository)
        self.init_repo_action = QAction("初始化仓库", self)
        self.init_repo_action.triggered.connect(self.init_repository)
        self.clone_repo_action = QAction("克隆仓库", self)
        self.clone_repo_action.triggered.connect(self.clone_repository)
        self.refresh_action = QAction("刷新", self)
        self.refresh_action.triggered.connect(self.refresh_all)
        self.copy_command_action = QAction("复制最后命令", self)
        self.copy_command_action.triggered.connect(self.copy_last_command)

        menu = self.menuBar().addMenu("文件")
        menu.addAction(self.open_repo_action)
        menu.addAction(self.init_repo_action)
        menu.addAction(self.clone_repo_action)
        menu.addSeparator()
        menu.addAction(self.refresh_action)

        tools = self.menuBar().addMenu("工具")
        tools.addAction(self.copy_command_action)
        tools.addAction("打开原生终端命令示例", self.show_terminal_help)

        appearance_menu = self.menuBar().addMenu("外观")
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        self.dark_theme_action = QAction("深色模式", self)
        self.dark_theme_action.setCheckable(True)
        self.light_theme_action = QAction("浅色模式", self)
        self.light_theme_action.setCheckable(True)
        self.dark_theme_action.setChecked(True)
        mode_group.addAction(self.dark_theme_action)
        mode_group.addAction(self.light_theme_action)
        self.dark_theme_action.triggered.connect(lambda: self.change_theme_mode("dark"))
        self.light_theme_action.triggered.connect(lambda: self.change_theme_mode("light"))
        appearance_menu.addAction(self.dark_theme_action)
        appearance_menu.addAction(self.light_theme_action)

        accent_menu = appearance_menu.addMenu("配色")
        accent_group = QActionGroup(self)
        accent_group.setExclusive(True)
        self.accent_actions = {}
        for accent_key, label in [("blue", "蓝色"), ("purple", "紫色"), ("green", "绿色"), ("orange", "橙色")]:
            action = QAction(label, self)
            action.setCheckable(True)
            if accent_key == "blue":
                action.setChecked(True)
            action.triggered.connect(lambda _=False, key=accent_key: self.change_theme_accent(key))
            accent_group.addAction(action)
            accent_menu.addAction(action)
            self.accent_actions[accent_key] = action

        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction("快捷键", self.show_shortcuts)
        help_menu.addAction("关于 Git Terminal", self.show_about)

        toolbar = QToolBar("主工具栏")
        toolbar.addAction(self.open_repo_action)
        toolbar.addAction(self.init_repo_action)
        toolbar.addAction(self.clone_repo_action)
        toolbar.addAction(self.refresh_action)
        self.addToolBar(toolbar)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.status_bar_label = QLabel("Repo: - | Branch: - | HEAD: - | Remote: - | Ahead: 0 | Behind: 0 | Dirty: 0 | Mode: -")
        self.status_bar_label.setObjectName("TopStatusLabel")
        self.status_bar_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_bar_label.setMinimumHeight(38)
        root.addWidget(self.status_bar_label)

        # Main layout: left sidebar | center vertical splitter | right sidebar.
        # The bottom command/log bar lives inside the center splitter, so sidebars
        # extend all the way to the bottom and the log bar aligns with the center.
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setHandleWidth(7)
        root.addWidget(self.main_splitter, 1)

        self.left_pane = QWidget()
        self.left_pane.setObjectName("LeftPane")
        self.left_pane.setMinimumWidth(36)
        self.left_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(self.left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.left_toggle_button = QPushButton("◀")
        self.left_toggle_button.setObjectName("CollapseButton")
        self.left_toggle_button.setToolTip("收起左侧栏")
        self.left_toggle_button.clicked.connect(self.toggle_left_sidebar)
        left_layout.addWidget(self._make_pane_header("导航", self.left_toggle_button))
        self.navigator = QTreeWidget()
        self.navigator.setHeaderLabel("Git Terminal")
        self.navigator.setMinimumWidth(0)
        self.navigator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._populate_navigator()
        self.navigator.itemClicked.connect(self._navigator_clicked)
        left_layout.addWidget(self.navigator, 1)
        self.main_splitter.addWidget(self.left_pane)

        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setChildrenCollapsible(True)
        self.center_splitter.setHandleWidth(7)
        self.center_splitter.setMinimumWidth(120)
        self.center_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.setMinimumWidth(120)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.center_splitter.addWidget(self.tabs)
        self._build_log_bar()
        self.center_splitter.addWidget(self.log_bar)
        self.center_splitter.setStretchFactor(0, 8)
        self.center_splitter.setStretchFactor(1, 2)
        self.center_splitter.setSizes([690, 220])
        self.main_splitter.addWidget(self.center_splitter)

        self.right_pane = QWidget()
        self.right_pane.setObjectName("RightPane")
        self.right_pane.setMinimumWidth(36)
        self.right_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(self.right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.right_toggle_button = QPushButton("▶")
        self.right_toggle_button.setObjectName("CollapseButton")
        self.right_toggle_button.setToolTip("收起右侧栏")
        self.right_toggle_button.clicked.connect(self.toggle_right_sidebar)
        right_layout.addWidget(self._make_pane_header("上下文操作", self.right_toggle_button, button_first=False))
        self.context_panel = QWidget()
        self.context_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        context_layout = QVBoxLayout(self.context_panel)
        context_layout.setContentsMargins(0, 0, 0, 0)
        self.context_buttons = []
        for text, handler in [
            ("git status -sb", lambda: self.run_git_command(["status", "-sb"], callback=lambda _: self.refresh_all())),
            ("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Fetch --all --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Pull --ff-only", lambda: self.run_git_command(["pull", "--ff-only"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Reflog", lambda: self.run_git_command(["reflog", "--date=iso"], callback=self.show_result_in_log)),
            ("Rescue Branch from HEAD@{1}", self.create_rescue_branch),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            context_layout.addWidget(btn)
            self.context_buttons.append(btn)
        context_layout.addStretch(1)
        right_layout.addWidget(self.context_panel, 1)
        self.main_splitter.addWidget(self.right_pane)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 6)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setSizes([260, 940, 300])

        self._build_workspace_tab()
        self._build_history_tab()
        self._build_branch_tab()
        self._build_remote_tab()
        self._build_tag_stash_tab()
        self._build_conflict_tab()
        self._build_advanced_tab()
        self._build_all_commands_tab()
        self._build_platform_tab()
        self._compact_ui_controls()

        self.setCentralWidget(central)

    def _make_pane_header(self, title: str, button: QPushButton, button_first: bool = True) -> QFrame:
        header = QFrame()
        header.setObjectName("PaneHeader")
        header.setMinimumHeight(38)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        label = QLabel(title)
        label.setObjectName("PaneTitle")
        if button_first:
            layout.addWidget(button)
            layout.addWidget(label, 1)
        else:
            layout.addWidget(label, 1)
            layout.addWidget(button)
        return header

    def _populate_navigator(self) -> None:
        groups = {
            "Workspace": ["Changed files", "Staged files", "Untracked files", "Ignored files"],
            "History": ["Current branch", "All branches", "Reflog", "Bisect"],
            "Refs": ["Local branches", "Remote branches", "Tags", "Worktrees"],
            "Remotes": ["origin", "upstream", "custom"],
            "Collaboration": ["GitHub", "Gitee", "GitLab", "Bitbucket", "Pull Requests", "Issues", "Releases", "CI"],
            "Advanced": ["Stash", "Submodules", "LFS", "Hooks", "Config", "Objects", "Maintenance", "Raw Commands"],
        }
        for group, children in groups.items():
            root = QTreeWidgetItem([group])
            self.navigator.addTopLevelItem(root)
            for child in children:
                root.addChild(QTreeWidgetItem([child]))
            root.setExpanded(True)

    def _build_workspace_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        lists = QSplitter(Qt.Orientation.Horizontal)
        self.changed_list = QListWidget()
        self.staged_list = QListWidget()
        self.untracked_list = QListWidget()
        for title, widget in [("Changed", self.changed_list), ("Staged", self.staged_list), ("Untracked", self.untracked_list)]:
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(widget)
            lists.addWidget(box)
        layout.addWidget(lists, 2)

        btns = QHBoxLayout()
        for text, handler in [
            ("Stage Selected", self.stage_selected),
            ("Unstage Selected", self.unstage_selected),
            ("Stage All", lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all())),
            ("Unstage All", lambda: self.run_git_command(["restore", "--staged", "."], callback=lambda _: self.refresh_all())),
            ("Restore Selected", self.restore_selected),
            ("Clean Untracked", self.clean_selected_untracked),
            ("Diff", self.show_selected_diff),
            ("Refresh", self.refresh_all),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            btns.addWidget(button)
        layout.addLayout(btns)

        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setPlaceholderText("选择文件后显示 git diff / git diff --staged")
        layout.addWidget(self.diff_view, 3)

        commit_box = QGroupBox("Commit")
        commit_layout = QHBoxLayout(commit_box)
        self.commit_message = QLineEdit()
        self.commit_message.setPlaceholderText("提交信息，例如 feat(auth): add login")
        commit_layout.addWidget(self.commit_message, 1)
        commit_button = QPushButton("git commit -m")
        commit_button.clicked.connect(self.commit_changes)
        amend_button = QPushButton("Amend --no-edit")
        amend_button.clicked.connect(lambda: self.run_git_command(["commit", "--amend", "--no-edit"], callback=lambda _: self.refresh_all()))
        commit_layout.addWidget(commit_button)
        commit_layout.addWidget(amend_button)
        layout.addWidget(commit_box)

        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.currentItemChanged.connect(lambda *_: self.show_selected_diff())
            widget.itemDoubleClicked.connect(lambda *_: self.show_selected_diff())

        self.tabs.addTab(page, "工作区")

    def _build_history_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.history_tree = QTreeWidget()
        self.history_tree.setColumnCount(6)
        self.history_tree.setHeaderLabels(["Graph", "Hash", "Date", "Author", "Refs", "Message"])
        self.history_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_tree.customContextMenuRequested.connect(self._commit_context_menu)
        self.history_tree.itemClicked.connect(self.show_commit_details)
        layout.addWidget(self.history_tree, 3)
        buttons = QHBoxLayout()
        for text, handler in [
            ("Log Current", lambda: self.refresh_history(all_branches=False)),
            ("Log --all", lambda: self.refresh_history(all_branches=True)),
            ("Show Commit", self.show_commit_details),
            ("Checkout Commit", self.checkout_selected_commit),
            ("Create Branch Here", self.branch_from_selected_commit),
            ("Cherry-pick", self.cherry_pick_selected_commit),
            ("Revert", self.revert_selected_commit),
            ("Reset --hard Here", self.reset_hard_selected_commit),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.commit_detail = QPlainTextEdit()
        self.commit_detail.setReadOnly(True)
        layout.addWidget(self.commit_detail, 2)
        self.tabs.addTab(page, "提交历史")

    def _build_branch_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.branch_view_tabs = QTabWidget()
        self.branch_view_tabs.setUsesScrollButtons(True)
        self.branch_view_tabs.tabBar().setExpanding(False)
        layout.addWidget(self.branch_view_tabs, 1)

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        self.branch_list = QListWidget()
        self.branch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.branch_list.customContextMenuRequested.connect(self._branch_context_menu)
        list_layout.addWidget(self.branch_list, 1)
        row = QHBoxLayout()
        self.new_branch_name = QLineEdit()
        self.new_branch_name.setPlaceholderText("新分支名")
        row.addWidget(self.new_branch_name)
        for text, handler in [
            ("Create", self.create_branch),
            ("Switch", self.switch_branch),
            ("Delete", self.delete_branch),
            ("Merge", self.merge_branch),
            ("Rebase", self.rebase_onto_branch),
            ("Push -u", self.push_branch_upstream),
            ("Pull", lambda: self.run_git_command(["pull"], callback=lambda _: self.refresh_all(), timeout=300)),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b)
        list_layout.addLayout(row)
        self.branch_view_tabs.addTab(list_page, "列表")

        graph_page = QWidget()
        graph_layout = QVBoxLayout(graph_page)
        graph_toolbar = QHBoxLayout()
        refresh_graph_btn = QPushButton("刷新图")
        refresh_graph_btn.clicked.connect(self.refresh_branch_graph)
        fit_graph_btn = QPushButton("适应视图")
        fit_graph_btn.clicked.connect(self.fit_branch_graph)
        graph_help = QLabel("提示：悬浮节点看信息，单击看详情，双击 checkout，右键更多操作；Ctrl+滚轮缩放。")
        graph_help.setWordWrap(True)
        graph_toolbar.addWidget(refresh_graph_btn)
        graph_toolbar.addWidget(fit_graph_btn)
        graph_toolbar.addWidget(graph_help, 1)
        graph_layout.addLayout(graph_toolbar)
        graph_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.branch_graph_view = CommitGraphView()
        self.branch_graph_view.commitSelected.connect(self.graph_commit_selected)
        self.branch_graph_view.commitActivated.connect(self.graph_checkout_commit)
        self.branch_graph_view.commitContextRequested.connect(self.graph_commit_context_menu)
        graph_splitter.addWidget(self.branch_graph_view)
        self.branch_graph_detail = QPlainTextEdit()
        self.branch_graph_detail.setReadOnly(True)
        self.branch_graph_detail.setPlaceholderText("单击图节点后显示 commit 详情")
        graph_splitter.addWidget(self.branch_graph_detail)
        graph_splitter.setStretchFactor(0, 5)
        graph_splitter.setStretchFactor(1, 2)
        graph_splitter.setSizes([780, 300])
        graph_layout.addWidget(graph_splitter, 1)
        self.branch_view_tabs.addTab(graph_page, "有向图")

        self.tabs.addTab(page, "分支")

    def _build_remote_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.remote_tree = QTreeWidget()
        self.remote_tree.setColumnCount(3)
        self.remote_tree.setHeaderLabels(["Remote", "Type", "URL"])
        layout.addWidget(self.remote_tree, 1)
        row = QHBoxLayout()
        for text, handler in [
            ("remote -v", self.refresh_remotes),
            ("Add", self.add_remote),
            ("Remove", self.remove_remote),
            ("Set URL", self.set_remote_url),
            ("Fetch", self.fetch_remote),
            ("Fetch --prune", lambda: self.run_git_command(["fetch", "--all", "--prune"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Push", lambda: self.run_git_command(["push"], callback=lambda _: self.refresh_all(), timeout=300)),
            ("Delete Remote Branch", self.delete_remote_branch),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b)
        layout.addLayout(row)
        self.remote_output = QPlainTextEdit()
        self.remote_output.setReadOnly(True)
        layout.addWidget(self.remote_output, 1)
        self.tabs.addTab(page, "远程")

    def _build_tag_stash_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)

        tag_box = QGroupBox("Tags")
        tag_layout = QVBoxLayout(tag_box)
        self.tag_list = QListWidget()
        tag_layout.addWidget(self.tag_list)
        self.new_tag_name = QLineEdit()
        self.new_tag_name.setPlaceholderText("v1.0.0")
        tag_layout.addWidget(self.new_tag_name)
        tag_buttons = QHBoxLayout()
        for text, handler in [
            ("Create", self.create_tag),
            ("Delete", self.delete_tag),
            ("Push", self.push_tag),
            ("Push --tags", lambda: self.run_git_command(["push", "--tags"], callback=lambda _: self.refresh_all(), timeout=300)),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            tag_buttons.addWidget(b)
        tag_layout.addLayout(tag_buttons)
        layout.addWidget(tag_box)

        stash_box = QGroupBox("Stash")
        stash_layout = QVBoxLayout(stash_box)
        self.stash_list = QListWidget()
        stash_layout.addWidget(self.stash_list)
        self.stash_message = QLineEdit()
        self.stash_message.setPlaceholderText("stash message")
        stash_layout.addWidget(self.stash_message)
        stash_buttons = QHBoxLayout()
        for text, handler in [
            ("Push -u", self.stash_push),
            ("Apply", self.stash_apply),
            ("Pop", self.stash_pop),
            ("Drop", self.stash_drop),
            ("Clear", lambda: self.run_git_command(["stash", "clear"], callback=lambda _: self.refresh_all())),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            stash_buttons.addWidget(b)
        stash_layout.addLayout(stash_buttons)
        layout.addWidget(stash_box)
        self.tabs.addTab(page, "标签 / Stash")

    def _build_conflict_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.conflict_list = QListWidget()
        layout.addWidget(self.conflict_list)
        row = QHBoxLayout()
        for text, handler in [
            ("Use ours", lambda: self.checkout_conflict_side("--ours")),
            ("Use theirs", lambda: self.checkout_conflict_side("--theirs")),
            ("Mark resolved", self.mark_conflict_resolved),
            ("Merge Continue", lambda: self.run_git_command(["merge", "--continue"], callback=lambda _: self.refresh_all())),
            ("Merge Abort", lambda: self.run_git_command(["merge", "--abort"], callback=lambda _: self.refresh_all())),
            ("Rebase Continue", lambda: self.run_git_command(["rebase", "--continue"], callback=lambda _: self.refresh_all())),
            ("Rebase Skip", lambda: self.run_git_command(["rebase", "--skip"], callback=lambda _: self.refresh_all())),
            ("Rebase Abort", lambda: self.run_git_command(["rebase", "--abort"], callback=lambda _: self.refresh_all())),
            ("Cherry-pick Continue", lambda: self.run_git_command(["cherry-pick", "--continue"], callback=lambda _: self.refresh_all())),
            ("Cherry-pick Abort", lambda: self.run_git_command(["cherry-pick", "--abort"], callback=lambda _: self.refresh_all())),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b)
        layout.addLayout(row)
        self.conflict_preview = QPlainTextEdit()
        self.conflict_preview.setReadOnly(True)
        layout.addWidget(self.conflict_preview, 1)
        self.conflict_list.currentItemChanged.connect(lambda *_: self.show_conflict_file())
        self.tabs.addTab(page, "冲突")

    def _build_advanced_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        object_box = QGroupBox("Object Inspector")
        form = QFormLayout(object_box)
        self.object_command = QComboBox()
        self.object_command.addItems(["cat-file -p", "cat-file -t", "cat-file -s", "ls-tree -r", "ls-files -s", "rev-parse --short", "show-ref", "for-each-ref", "hash-object", "commit-tree", "write-tree"])
        self.object_target = QLineEdit()
        self.object_target.setPlaceholderText("HEAD / HEAD^{tree} / path / hash")
        form.addRow("命令", self.object_command)
        form.addRow("对象或参数", self.object_target)
        run_obj = QPushButton("Run Object Command")
        run_obj.clicked.connect(self.run_object_command)
        form.addRow(run_obj)
        layout.addWidget(object_box)

        maintenance_box = QGroupBox("Repository Maintenance")
        maintenance_layout = QHBoxLayout(maintenance_box)
        for text, args in [
            ("count-objects -vH", ["count-objects", "-vH"]),
            ("fsck --full", ["fsck", "--full"]),
            ("gc", ["gc"]),
            ("reflog", ["reflog", "--date=iso"]),
            ("archive HEAD", ["archive", "--format=zip", "HEAD", "-o", "git-terminal-archive.zip"]),
            ("bundle --all", ["bundle", "create", "git-terminal.bundle", "--all"]),
            ("maintenance run", ["maintenance", "run"]),
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, a=args: self.run_git_command(a, callback=self.show_result_in_log, timeout=300))
            maintenance_layout.addWidget(b)
        layout.addWidget(maintenance_box)

        config_box = QGroupBox("Config / Hooks / LFS / Submodule 快捷入口")
        config_layout = QHBoxLayout(config_box)
        for text, args in [
            ("config --list --show-origin", ["config", "--list", "--show-origin"]),
            ("submodule status", ["submodule", "status", "--recursive"]),
            ("lfs status", ["lfs", "status"]),
            ("hooks path", ["config", "--get", "core.hooksPath"]),
            ("ignored files", ["status", "--ignored", "-s"]),
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, a=args: self.run_git_command(a, callback=self.show_result_in_log, timeout=300))
            config_layout.addWidget(b)
        layout.addWidget(config_box)

        self.advanced_output = QPlainTextEdit()
        self.advanced_output.setReadOnly(True)
        layout.addWidget(self.advanced_output, 1)
        self.tabs.addTab(page, "专家模式")

    def _build_all_commands_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("完整 Git 命令入口：从本机 git help -a 动态发现命令，并叠加内置常用选项。任何 Git 子命令都可以在这里带参数执行。")
        header.setWordWrap(True)
        layout.addWidget(header)

        form_box = QGroupBox("高级参数面板")
        form = QFormLayout(form_box)
        self.command_combo = QComboBox()
        for name, spec in self.command_catalog.items():
            self.command_combo.addItem(f"{name}  [{spec.category}]", name)
        self.command_combo.currentIndexChanged.connect(self._command_changed)
        self.command_args = QLineEdit()
        self.command_args.setPlaceholderText("参数，例如 --all --prune 或 origin main")
        self.command_args.textChanged.connect(self.update_command_preview)
        self.options_box = QGroupBox("常用选项")
        self.options_layout = QHBoxLayout(self.options_box)
        self.options_layout.addStretch(1)
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        self.command_desc = QLabel()
        self.command_desc.setWordWrap(True)
        form.addRow("Git 命令", self.command_combo)
        form.addRow("参数", self.command_args)
        form.addRow(self.options_box)
        form.addRow("预览", self.command_preview)
        form.addRow("说明", self.command_desc)
        layout.addWidget(form_box)

        examples_box = QGroupBox("示例")
        examples_layout = QVBoxLayout(examples_box)
        self.command_examples = QListWidget()
        self.command_examples.itemDoubleClicked.connect(self.use_command_example)
        examples_layout.addWidget(self.command_examples)
        layout.addWidget(examples_box)

        row = QHBoxLayout()
        for text, handler in [
            ("Run", self.run_advanced_command),
            ("Copy", lambda: QApplication.clipboard().setText(self.command_preview.text())),
            ("Open Help", self.open_selected_command_help),
            ("Refresh git help -a", self.reload_command_catalog),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            row.addWidget(b)
        layout.addLayout(row)

        self.all_commands_output = QPlainTextEdit()
        self.all_commands_output.setReadOnly(True)
        layout.addWidget(self.all_commands_output, 1)
        self.tabs.addTab(page, "全部命令")
        self._command_changed()

    def _build_platform_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "平台能力是增强模块：本地 Git 功能无需登录；GitHub 可优先调用 gh CLI，GitLab 可调用 glab CLI，"
            "Gitee/Bitbucket 可通过 token 或自定义 API 扩展。这里保留命令透明输出，不保存明文 token。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        for text, cmd in [
            ("gh auth status", ["gh", "auth", "status"]),
            ("gh repo list", ["gh", "repo", "list", "--limit", "50"]),
            ("gh pr list", ["gh", "pr", "list"]),
            ("gh issue list", ["gh", "issue", "list"]),
            ("gh release list", ["gh", "release", "list"]),
            ("glab auth status", ["glab", "auth", "status"]),
            ("glab mr list", ["glab", "mr", "list"]),
            ("glab issue list", ["glab", "issue", "list"]),
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, c=cmd: self.run_external_command(c))
            row.addWidget(b)
        layout.addLayout(row)

        gitee_box = QGroupBox("Gitee / 自定义平台 API 扩展点")
        gitee_form = QFormLayout(gitee_box)
        self.gitee_token = QLineEdit()
        self.gitee_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.gitee_token.setPlaceholderText("不建议长期明文保存；生产版应接入系统 Keychain")
        self.gitee_user = QLineEdit()
        self.gitee_user.setPlaceholderText("用户名 / org")
        gitee_form.addRow("Gitee Token", self.gitee_token)
        gitee_form.addRow("用户/组织", self.gitee_user)
        gitee_btns = QHBoxLayout()
        check_btn = QPushButton("检查 token / user repos")
        check_btn.clicked.connect(self.gitee_list_repos)
        gitee_btns.addWidget(check_btn)
        gitee_form.addRow(gitee_btns)
        layout.addWidget(gitee_box)

        self.platform_output = QPlainTextEdit()
        self.platform_output.setReadOnly(True)
        layout.addWidget(self.platform_output, 1)
        self.tabs.addTab(page, "平台")

    def _build_log_bar(self) -> None:
        self.log_bar = QGroupBox("Command Bar / Log")
        self.log_bar.setMinimumHeight(42)
        self.log_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self.log_bar)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.bottom_toggle_button = QPushButton("▼")
        self.bottom_toggle_button.setObjectName("CollapseButton")
        self.bottom_toggle_button.setToolTip("收起底部栏")
        self.bottom_toggle_button.clicked.connect(self.toggle_bottom_bar)
        title = QLabel("命令栏 / 日志")
        title.setObjectName("PaneTitle")
        header.addWidget(self.bottom_toggle_button)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        self.log_content = QWidget()
        content_layout = QVBoxLayout(self.log_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        cmd_row = QHBoxLayout()
        self.raw_command = QLineEdit()
        self.raw_command.setPlaceholderText(":git status -sb  或  status -sb")
        self.raw_command.returnPressed.connect(self.run_raw_command)
        run_btn = QPushButton("Run Raw Git")
        run_btn.clicked.connect(self.run_raw_command)
        cmd_row.addWidget(QLabel(":"))
        cmd_row.addWidget(self.raw_command, 1)
        cmd_row.addWidget(run_btn)
        content_layout.addLayout(cmd_row)
        self.command_log = QPlainTextEdit()
        self.command_log.setReadOnly(True)
        self.command_log.setMaximumBlockCount(5000)
        self.command_log.setMinimumHeight(80)
        self.command_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.command_log, 1)
        layout.addWidget(self.log_content, 1)

    def _compact_ui_controls(self) -> None:
        """Let the VS Code-like splitters win over verbose control rows.

        Many tabs contain long button captions. If Qt uses their sizeHint as a
        hard layout minimum, the center pane becomes too wide and sidebars cannot
        expand. Mark these controls as horizontally shrinkable; text can clip at
        very small widths, but the user can freely resize panes.
        """
        for button in self.findChildren(QPushButton):
            if button.objectName() == "CollapseButton":
                continue
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            if button.text() and not button.toolTip():
                button.setToolTip(button.text())
        for line_edit in self.findChildren(QLineEdit):
            line_edit.setMinimumWidth(0)
            line_edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        for tree in self.findChildren(QTreeWidget):
            tree.setMinimumWidth(0)
            tree.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        for list_widget in self.findChildren(QListWidget):
            list_widget.setMinimumWidth(0)
            list_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.tabs.setMinimumWidth(120)
        self.center_splitter.setMinimumWidth(120)

    def toggle_left_sidebar(self) -> None:
        sizes = self.main_splitter.sizes()
        if not self._left_collapsed:
            self._last_left_width = max(sizes[0], 180) if sizes else self._last_left_width
            self.navigator.setVisible(False)
            self.left_pane.setMaximumWidth(44)
            self.left_toggle_button.setText("▶")
            self.left_toggle_button.setToolTip("展开左侧栏")
            self._left_collapsed = True
            if len(sizes) == 3:
                self.main_splitter.setSizes([44, sizes[1] + max(sizes[0] - 44, 0), sizes[2]])
        else:
            self.left_pane.setMaximumWidth(16777215)
            self.navigator.setVisible(True)
            self.left_toggle_button.setText("◀")
            self.left_toggle_button.setToolTip("收起左侧栏")
            self._left_collapsed = False
            sizes = self.main_splitter.sizes()
            if len(sizes) == 3:
                self.main_splitter.setSizes([self._last_left_width, max(sizes[1] - self._last_left_width + 44, 300), sizes[2]])

    def toggle_right_sidebar(self) -> None:
        sizes = self.main_splitter.sizes()
        if not self._right_collapsed:
            self._last_right_width = max(sizes[2], 220) if len(sizes) == 3 else self._last_right_width
            self.context_panel.setVisible(False)
            self.right_pane.setMaximumWidth(44)
            self.right_toggle_button.setText("◀")
            self.right_toggle_button.setToolTip("展开右侧栏")
            self._right_collapsed = True
            if len(sizes) == 3:
                self.main_splitter.setSizes([sizes[0], sizes[1] + max(sizes[2] - 44, 0), 44])
        else:
            self.right_pane.setMaximumWidth(16777215)
            self.context_panel.setVisible(True)
            self.right_toggle_button.setText("▶")
            self.right_toggle_button.setToolTip("收起右侧栏")
            self._right_collapsed = False
            sizes = self.main_splitter.sizes()
            if len(sizes) == 3:
                self.main_splitter.setSizes([sizes[0], max(sizes[1] - self._last_right_width + 44, 300), self._last_right_width])

    def toggle_bottom_bar(self) -> None:
        sizes = self.center_splitter.sizes()
        if not self._bottom_collapsed:
            self._last_bottom_height = max(sizes[1], 160) if len(sizes) == 2 else self._last_bottom_height
            self.log_content.setVisible(False)
            self.log_bar.setMaximumHeight(50)
            self.bottom_toggle_button.setText("▲")
            self.bottom_toggle_button.setToolTip("展开底部栏")
            self._bottom_collapsed = True
            if len(sizes) == 2:
                self.center_splitter.setSizes([sizes[0] + max(sizes[1] - 50, 0), 50])
        else:
            self.log_bar.setMaximumHeight(16777215)
            self.log_content.setVisible(True)
            self.bottom_toggle_button.setText("▼")
            self.bottom_toggle_button.setToolTip("收起底部栏")
            self._bottom_collapsed = False
            sizes = self.center_splitter.sizes()
            if len(sizes) == 2:
                self.center_splitter.setSizes([max(sizes[0] - self._last_bottom_height + 50, 300), self._last_bottom_height])

    def change_theme_mode(self, mode: str) -> None:
        self.theme_mode = mode
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)

    def change_theme_accent(self, accent: str) -> None:
        self.theme_accent = accent
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self, self.theme_mode, self.theme_accent)

    def _wire_shortcuts(self) -> None:
        self.open_repo_action.setShortcut(QKeySequence("Ctrl+O"))
        self.refresh_action.setShortcut(QKeySequence("F5"))
        self.stage_all_action = QAction("Stage All", self)
        self.stage_all_action.setShortcut(QKeySequence("A"))
        self.stage_all_action.triggered.connect(lambda: self.run_git_command(["add", "-A"], callback=lambda _: self.refresh_all()))
        self.addAction(self.stage_all_action)

    # ------------------------------------------------------------------
    # General command execution
    # ------------------------------------------------------------------
    def detect_environment(self) -> None:
        git = self.runner.detect_git()
        self.append_log("Environment check")
        if git.ok:
            self.append_log(f"✓ {git.output}")
        else:
            self.append_log("✗ Git not found. 请先安装 Git 后重新检测。")
        for args in (["config", "--global", "user.name"], ["config", "--global", "user.email"], ["config", "--global", "init.defaultBranch"], ["config", "--global", "credential.helper"]):
            result = self.runner.run(args, cwd=None)
            self.append_log(f"$ git {' '.join(args)}\n{result.output or '(empty)'}")
        if shutil.which("ssh"):
            self.append_log("✓ ssh found")
        else:
            self.append_log("⚠ ssh not found")
        if shutil.which("gh"):
            self.append_log("✓ GitHub CLI gh found")
        else:
            self.append_log("ℹ GitHub CLI gh not found；平台功能仍可通过 Git remote 使用。")

    def confirm_risk(self, args: List[str]) -> bool:
        assessment = classify_git_command(args)
        command_text = "git " + " ".join(shlex.quote(a) for a in args)
        if assessment.level != RiskLevel.HIGH:
            return True
        message = (
            f"{assessment.title}\n\n"
            f"原因：{assessment.reason}\n\n"
            f"Will run:\n{command_text}\n\n"
            f"请输入 {assessment.confirmation_word} 继续。"
        )
        text, ok = QInputDialog.getText(self, "危险操作确认", message)
        if not ok or text.strip() != assessment.confirmation_word:
            self.append_log(f"已取消高风险命令：{command_text}")
            return False
        return True

    def run_git_command(
        self,
        args: List[str],
        callback: Optional[Callable[[GitResult], None]] = None,
        timeout: int = 120,
        risk_check: bool = True,
    ) -> None:
        if not args:
            return
        if args[0] == "git":
            args = args[1:]
        if risk_check and not self.confirm_risk(args):
            return
        command_text = "git " + " ".join(shlex.quote(a) for a in args)
        self.append_log(f"Will run:\n{command_text}")
        thread = QThread(self)
        worker = GitCommandWorker(self.runner, args, callback, timeout)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._command_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        # Keep Python references while the command runs, then clean them before Qt deletes the C++ object.
        self._threads.append((thread, worker))
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_thread(t, w))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _command_finished(self, result: GitResult, callback: Optional[Callable[[GitResult], None]]) -> None:
        status = "✓" if result.ok else "✗"
        self.append_log(f"{status} {result.command_text}\n{result.output or '(no output)'}")
        if callback:
            callback(result)

    def _cleanup_thread(self, thread: QThread, worker: GitCommandWorker) -> None:
        # Do not call thread.isRunning() here: on Windows/PyQt the wrapped C++
        # QThread may already be scheduled for deletion, which caused
        # RuntimeError: wrapped C/C++ object of type QThread has been deleted.
        self._threads = [(t, w) for (t, w) in self._threads if t is not thread and w is not worker]

    def run_raw_command(self) -> None:
        raw = self.raw_command.text().strip()
        if not raw:
            return
        if raw.startswith(":"):
            raw = raw[1:].strip()
        parts = shlex.split(raw)
        if parts and parts[0] == "git":
            parts = parts[1:]
        self.run_git_command(parts, callback=lambda _: self.refresh_all(), timeout=300)

    def run_external_command(self, cmd: List[str]) -> None:
        self.append_log("Will run external:\n" + " ".join(shlex.quote(x) for x in cmd))
        try:
            proc = subprocess.run(cmd, cwd=self.runner.cwd(), capture_output=True, text=True, timeout=120)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.platform_output.setPlainText(out.strip() or "(no output)")
            self.append_log(("✓" if proc.returncode == 0 else "✗") + " " + " ".join(cmd) + "\n" + (out.strip() or "(no output)"))
        except Exception as exc:
            self.platform_output.setPlainText(str(exc))
            self.append_log("✗ " + str(exc))

    def append_log(self, text: str) -> None:
        if not hasattr(self, "command_log"):
            return
        self.command_log.appendPlainText(text.rstrip() + "\n")
        self.command_log.moveCursor(QTextCursor.MoveOperation.End)

    def show_result_in_log(self, result: GitResult) -> None:
        if hasattr(self, "advanced_output"):
            self.advanced_output.setPlainText(result.output)
        if hasattr(self, "all_commands_output"):
            self.all_commands_output.setPlainText(result.output)

    # ------------------------------------------------------------------
    # Repository lifecycle
    # ------------------------------------------------------------------
    def open_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "打开 Git 仓库")
        if not directory:
            return
        self.runner.set_repo(directory)
        check = self.runner.run(["rev-parse", "--is-inside-work-tree"])
        if not check.ok:
            answer = QMessageBox.question(self, "不是 Git 仓库", "该目录不是 Git 仓库。是否执行 git init？")
            if answer == QMessageBox.StandardButton.Yes:
                self.run_git_command(["init"], callback=lambda _: self.refresh_all())
            else:
                self.runner.repo_path = None
                return
        self.refresh_all()

    def init_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择要初始化的目录")
        if not directory:
            return
        self.runner.set_repo(directory)
        self.run_git_command(["init"], callback=lambda _: self.refresh_all())

    def clone_repository(self) -> None:
        dialog = CloneDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        url = dialog.url.text().strip()
        dest = dialog.dest.text().strip()
        if not url or not dest:
            QMessageBox.warning(self, "缺少参数", "请输入远程 URL 和目标目录。")
            return
        parent = Path(dest)
        self.runner.repo_path = parent
        self.run_git_command(["clone", url], callback=lambda r: self._after_clone(r, parent), timeout=900)

    def _after_clone(self, result: GitResult, parent: Path) -> None:
        if result.ok:
            # Infer repository directory from clone URL.
            name = result.command[-1].rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
            candidate = parent / name
            if candidate.exists():
                self.runner.set_repo(candidate)
        self.refresh_all()

    def refresh_all(self) -> None:
        self.update_top_status()
        self.refresh_worktree()
        self.refresh_history(all_branches=True)
        self.refresh_branches()
        self.refresh_branch_graph()
        self.refresh_remotes()
        self.refresh_tags_stash()
        self.refresh_conflicts()

    def update_top_status(self) -> None:
        summary = self.runner.summarize()
        remote = ",".join(summary.remotes) if summary.remotes else "-"
        self.status_bar_label.setText(
            f"Repo: {summary.name} | Branch: {summary.branch} | HEAD: {summary.head} | "
            f"Remote: {remote} | Upstream: {summary.upstream} | Ahead: {summary.ahead} | "
            f"Behind: {summary.behind} | Dirty: {summary.dirty} | Mode: {summary.mode}"
        )

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------
    def refresh_worktree(self) -> None:
        for widget in (self.changed_list, self.staged_list, self.untracked_list):
            widget.clear()
        if not self.runner.repo_path:
            return
        for item in self.runner.parse_status():
            list_item = QListWidgetItem(item.display)
            list_item.setData(Qt.ItemDataRole.UserRole, item.path)
            if item.untracked:
                self.untracked_list.addItem(list_item)
            else:
                if item.staged:
                    staged_item = QListWidgetItem(item.display)
                    staged_item.setData(Qt.ItemDataRole.UserRole, item.path)
                    self.staged_list.addItem(staged_item)
                if item.changed:
                    self.changed_list.addItem(list_item)

    def _selected_status_item(self) -> Tuple[Optional[str], str]:
        for name, widget in [("staged", self.staged_list), ("changed", self.changed_list), ("untracked", self.untracked_list)]:
            item = widget.currentItem()
            if item and widget.hasFocus():
                return item.data(Qt.ItemDataRole.UserRole), name
        # Fallback: any current item.
        for name, widget in [("staged", self.staged_list), ("changed", self.changed_list), ("untracked", self.untracked_list)]:
            item = widget.currentItem()
            if item:
                return item.data(Qt.ItemDataRole.UserRole), name
        return None, ""

    def stage_selected(self) -> None:
        path, _ = self._selected_status_item()
        if path:
            self.run_git_command(["add", "--", path], callback=lambda _: self.refresh_all())

    def unstage_selected(self) -> None:
        path, _ = self._selected_status_item()
        if path:
            self.run_git_command(["restore", "--staged", "--", path], callback=lambda _: self.refresh_all())

    def restore_selected(self) -> None:
        path, area = self._selected_status_item()
        if not path:
            return
        if area == "staged":
            self.run_git_command(["restore", "--staged", "--", path], callback=lambda _: self.refresh_all())
        else:
            self.run_git_command(["restore", "--", path], callback=lambda _: self.refresh_all())

    def clean_selected_untracked(self) -> None:
        path, area = self._selected_status_item()
        if path and area == "untracked":
            self.run_git_command(["clean", "-f", "--", path], callback=lambda _: self.refresh_all())

    def show_selected_diff(self) -> None:
        path, area = self._selected_status_item()
        if not path:
            return
        args = ["diff", "--staged", "--", path] if area == "staged" else ["diff", "--", path]
        result = self.runner.run(args)
        self.diff_view.setPlainText(result.output or "(no diff)")

    def commit_changes(self) -> None:
        msg = self.commit_message.text().strip()
        if not msg:
            QMessageBox.warning(self, "缺少提交信息", "请输入 commit message。")
            return
        self.run_git_command(["commit", "-m", msg], callback=lambda _: self.refresh_all())

    # ------------------------------------------------------------------
    # History and commit graph
    # ------------------------------------------------------------------
    def refresh_history(self, all_branches: bool = True) -> None:
        self.history_tree.clear()
        if not self.runner.repo_path:
            return
        args = [
            "log",
            "--graph",
            "--date=short",
            "--pretty=format:%h%x09%H%x09%ad%x09%an%x09%D%x09%s",
            "-n",
            "300",
        ]
        if all_branches:
            args.insert(-2, "--all")
        result = self.runner.run(args)
        if not result.ok:
            self.commit_detail.setPlainText(result.output)
            return
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                self.history_tree.addTopLevelItem(QTreeWidgetItem([line, "", "", "", "", ""]))
                continue
            graph_hash, full_hash, date, author, refs, message = parts[:6]
            # graph_hash can contain graph characters before the abbreviated hash.
            item = QTreeWidgetItem([graph_hash, graph_hash.split()[-1] if graph_hash.split() else "", date, author, refs, message])
            item.setData(0, Qt.ItemDataRole.UserRole, full_hash)
            self.history_tree.addTopLevelItem(item)
        for i in range(6):
            self.history_tree.resizeColumnToContents(i)

    def _selected_commit_hash(self) -> Optional[str]:
        item = self.history_tree.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def show_commit_details(self, *_args) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        result = self.runner.run(["show", "--stat", "--patch", "--pretty=fuller", commit])
        self.commit_detail.setPlainText(result.output)

    def checkout_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["checkout", commit], callback=lambda _: self.refresh_all())

    def branch_from_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        name, ok = QInputDialog.getText(self, "创建分支", "分支名：")
        if ok and name.strip():
            self.run_git_command(["switch", "-c", name.strip(), commit], callback=lambda _: self.refresh_all())

    def cherry_pick_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["cherry-pick", commit], callback=lambda _: self.refresh_all())

    def revert_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["revert", commit], callback=lambda _: self.refresh_all())

    def reset_hard_selected_commit(self) -> None:
        commit = self._selected_commit_hash()
        if commit:
            self.run_git_command(["reset", "--hard", commit], callback=lambda _: self.refresh_all())

    def _commit_context_menu(self, pos: QPoint) -> None:
        commit = self._selected_commit_hash()
        if not commit:
            return
        menu = QMenu(self)
        menu.addAction("Checkout this commit", self.checkout_selected_commit)
        menu.addAction("Create branch here", self.branch_from_selected_commit)
        menu.addAction("Cherry-pick into current branch", self.cherry_pick_selected_commit)
        menu.addAction("Revert this commit", self.revert_selected_commit)
        menu.addAction("Reset current branch --hard here", self.reset_hard_selected_commit)
        menu.addAction("Compare with HEAD", lambda: self.run_git_command(["diff", "HEAD", commit], callback=self.show_result_in_log))
        menu.addAction("Copy commit hash", lambda: QApplication.clipboard().setText(commit))
        menu.addAction("Show raw object", lambda: self.run_git_command(["cat-file", "-p", commit], callback=self.show_result_in_log))
        menu.exec(self.history_tree.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------
    def refresh_branches(self) -> None:
        self.branch_list.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["branch", "-a", "-vv", "--no-color"])
        if result.ok:
            for line in result.stdout.splitlines():
                self.branch_list.addItem(line)

    def refresh_branch_graph(self) -> None:
        if not hasattr(self, "branch_graph_view"):
            return
        if not self.runner.repo_path:
            self.branch_graph_view.set_commits([])
            return
        result = self.runner.run([
            "log",
            "--topo-order",
            "--all",
            "--parents",
            "--date=short",
            "--pretty=format:%H%x09%P%x09%h%x09%ad%x09%an%x09%D%x09%s",
            "-n",
            "260",
        ])
        commits: List[GraphCommit] = []
        if result.ok:
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                full_hash, parent_text, short_hash, date, author, refs, message = parts[:7]
                parents = [p for p in parent_text.split() if p]
                commits.append(GraphCommit(full_hash, parents, short_hash, date, author, refs, message))
        self.branch_graph_view.set_commits(commits)
        if not commits:
            self.branch_graph_detail.setPlainText(result.output if not result.ok else "没有提交历史。")

    def fit_branch_graph(self) -> None:
        if hasattr(self, "branch_graph_view") and self.branch_graph_view.scene() is not None:
            rect = self.branch_graph_view.scene().sceneRect()
            if rect.isValid() and not rect.isEmpty():
                self.branch_graph_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def graph_commit_selected(self, commit_hash: str) -> None:
        result = self.runner.run(["show", "--stat", "--pretty=fuller", commit_hash])
        self.branch_graph_detail.setPlainText(result.output)

    def graph_checkout_commit(self, commit_hash: str) -> None:
        self.run_git_command(["checkout", commit_hash], callback=lambda _: self.refresh_all())

    def graph_create_branch_from_commit(self, commit_hash: str) -> None:
        name, ok = QInputDialog.getText(self, "从图节点创建分支", "分支名：")
        if ok and name.strip():
            self.run_git_command(["switch", "-c", name.strip(), commit_hash], callback=lambda _: self.refresh_all())

    def graph_commit_context_menu(self, commit_hash: str, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Checkout this commit", lambda: self.graph_checkout_commit(commit_hash))
        menu.addAction("Create branch here", lambda: self.graph_create_branch_from_commit(commit_hash))
        menu.addAction("Cherry-pick into current branch", lambda: self.run_git_command(["cherry-pick", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Revert this commit", lambda: self.run_git_command(["revert", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Reset current branch --hard here", lambda: self.run_git_command(["reset", "--hard", commit_hash], callback=lambda _: self.refresh_all()))
        menu.addAction("Compare with HEAD", lambda: self.run_git_command(["diff", "HEAD", commit_hash], callback=self.show_result_in_log))
        menu.addAction("Copy commit hash", lambda: QApplication.clipboard().setText(commit_hash))
        menu.addAction("Show raw object", lambda: self.run_git_command(["cat-file", "-p", commit_hash], callback=self.show_result_in_log))
        menu.exec(pos)

    def _selected_branch_name(self) -> Optional[str]:
        item = self.branch_list.currentItem()
        if not item:
            return None
        text = item.text().strip()
        if text.startswith("*"):
            text = text[1:].strip()
        # Remove metadata after whitespace / [upstream]
        if " " in text:
            text = text.split()[0]
        return text

    def create_branch(self) -> None:
        name = self.new_branch_name.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少分支名", "请输入分支名。")
            return
        self.run_git_command(["branch", name], callback=lambda _: self.refresh_all())

    def switch_branch(self) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        if name.startswith("remotes/"):
            local = name.split("/", 2)[-1]
            self.run_git_command(["switch", "--track", name], callback=lambda _: self.refresh_all())
        else:
            self.run_git_command(["switch", name], callback=lambda _: self.refresh_all())

    def delete_branch(self) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        if name.startswith("remotes/"):
            QMessageBox.information(self, "远程分支", "请在远程页使用 Delete Remote Branch。")
            return
        self.run_git_command(["branch", "-D", name], callback=lambda _: self.refresh_all())

    def merge_branch(self) -> None:
        name = self._selected_branch_name()
        if name:
            self.run_git_command(["merge", name], callback=lambda _: self.refresh_all())

    def rebase_onto_branch(self) -> None:
        name = self._selected_branch_name()
        if name:
            self.run_git_command(["rebase", name], callback=lambda _: self.refresh_all())

    def push_branch_upstream(self) -> None:
        name = self._selected_branch_name()
        if name and not name.startswith("remotes/"):
            remote, ok = QInputDialog.getText(self, "Push upstream", "remote：", text="origin")
            if ok and remote.strip():
                self.run_git_command(["push", "-u", remote.strip(), name], callback=lambda _: self.refresh_all(), timeout=300)

    def _branch_context_menu(self, pos: QPoint) -> None:
        name = self._selected_branch_name()
        if not name:
            return
        menu = QMenu(self)
        menu.addAction("Switch to branch", self.switch_branch)
        menu.addAction("Merge into current branch", self.merge_branch)
        menu.addAction("Rebase current branch onto this branch", self.rebase_onto_branch)
        menu.addAction("Push branch", self.push_branch_upstream)
        menu.addAction("Delete branch", self.delete_branch)
        menu.addAction("Compare with current branch", lambda: self.run_git_command(["diff", "HEAD", name], callback=self.show_result_in_log))
        menu.addAction("Copy branch name", lambda: QApplication.clipboard().setText(name))
        menu.exec(self.branch_list.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Remotes
    # ------------------------------------------------------------------
    def refresh_remotes(self) -> None:
        self.remote_tree.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["remote", "-v"])
        self.remote_output.setPlainText(result.output)
        if result.ok:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    remote, url, typ = parts[0], parts[1], parts[2].strip("()")
                    self.remote_tree.addTopLevelItem(QTreeWidgetItem([remote, typ, url]))
            for i in range(3):
                self.remote_tree.resizeColumnToContents(i)

    def _selected_remote(self) -> Optional[str]:
        item = self.remote_tree.currentItem()
        return item.text(0) if item else None

    def add_remote(self) -> None:
        d = RemoteDialog("Add Remote", self)
        if d.exec() == QDialog.DialogCode.Accepted:
            name, url = d.name.text().strip(), d.url.text().strip()
            if name and url:
                self.run_git_command(["remote", "add", name, url], callback=lambda _: self.refresh_all())

    def remove_remote(self) -> None:
        remote = self._selected_remote()
        if remote:
            self.run_git_command(["remote", "remove", remote], callback=lambda _: self.refresh_all())

    def set_remote_url(self) -> None:
        remote = self._selected_remote()
        if not remote:
            return
        url, ok = QInputDialog.getText(self, "Set Remote URL", f"{remote} URL：")
        if ok and url.strip():
            self.run_git_command(["remote", "set-url", remote, url.strip()], callback=lambda _: self.refresh_all())

    def fetch_remote(self) -> None:
        remote = self._selected_remote() or "--all"
        self.run_git_command(["fetch", remote], callback=lambda _: self.refresh_all(), timeout=300)

    def delete_remote_branch(self) -> None:
        remote, ok = QInputDialog.getText(self, "Delete Remote Branch", "remote：", text="origin")
        if not ok or not remote.strip():
            return
        branch, ok = QInputDialog.getText(self, "Delete Remote Branch", "远程分支名：")
        if ok and branch.strip():
            self.run_git_command(["push", remote.strip(), "--delete", branch.strip()], callback=lambda _: self.refresh_all(), timeout=300)

    # ------------------------------------------------------------------
    # Tags and Stash
    # ------------------------------------------------------------------
    def refresh_tags_stash(self) -> None:
        self.tag_list.clear()
        self.stash_list.clear()
        if not self.runner.repo_path:
            return
        tags = self.runner.run(["tag", "--list", "--sort=-creatordate"])
        if tags.ok:
            self.tag_list.addItems([x for x in tags.stdout.splitlines() if x.strip()])
        stash = self.runner.run(["stash", "list"])
        if stash.ok:
            self.stash_list.addItems([x for x in stash.stdout.splitlines() if x.strip()])

    def _selected_tag(self) -> Optional[str]:
        item = self.tag_list.currentItem()
        return item.text() if item else None

    def create_tag(self) -> None:
        tag = self.new_tag_name.text().strip()
        if tag:
            self.run_git_command(["tag", "-a", tag, "-m", tag], callback=lambda _: self.refresh_all())

    def delete_tag(self) -> None:
        tag = self._selected_tag()
        if tag:
            self.run_git_command(["tag", "-d", tag], callback=lambda _: self.refresh_all())

    def push_tag(self) -> None:
        tag = self._selected_tag()
        if tag:
            remote, ok = QInputDialog.getText(self, "Push Tag", "remote：", text="origin")
            if ok and remote.strip():
                self.run_git_command(["push", remote.strip(), tag], callback=lambda _: self.refresh_all(), timeout=300)

    def stash_push(self) -> None:
        msg = self.stash_message.text().strip() or "Git Terminal stash"
        self.run_git_command(["stash", "push", "-u", "-m", msg], callback=lambda _: self.refresh_all())

    def _selected_stash_ref(self) -> Optional[str]:
        item = self.stash_list.currentItem()
        if not item:
            return None
        return item.text().split(":", 1)[0]

    def stash_apply(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "apply", ref], callback=lambda _: self.refresh_all())

    def stash_pop(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "pop", ref], callback=lambda _: self.refresh_all())

    def stash_drop(self) -> None:
        ref = self._selected_stash_ref()
        if ref:
            self.run_git_command(["stash", "drop", ref], callback=lambda _: self.refresh_all())

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------
    def refresh_conflicts(self) -> None:
        self.conflict_list.clear()
        if not self.runner.repo_path:
            return
        result = self.runner.run(["status", "--porcelain=v1"])
        if not result.ok:
            return
        conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        for line in result.stdout.splitlines():
            if len(line) >= 4 and line[:2] in conflict_codes:
                item = QListWidgetItem(line)
                item.setData(Qt.ItemDataRole.UserRole, line[3:])
                self.conflict_list.addItem(item)

    def _selected_conflict_path(self) -> Optional[str]:
        item = self.conflict_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def show_conflict_file(self) -> None:
        path = self._selected_conflict_path()
        if not path:
            return
        full = Path(self.runner.cwd() or ".") / path
        try:
            self.conflict_preview.setPlainText(full.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            self.conflict_preview.setPlainText(str(exc))

    def checkout_conflict_side(self, side: str) -> None:
        path = self._selected_conflict_path()
        if path:
            self.run_git_command(["checkout", side, "--", path], callback=lambda _: self.refresh_all())

    def mark_conflict_resolved(self) -> None:
        path = self._selected_conflict_path()
        if path:
            self.run_git_command(["add", "--", path], callback=lambda _: self.refresh_all())

    # ------------------------------------------------------------------
    # Advanced / all commands
    # ------------------------------------------------------------------
    def run_object_command(self) -> None:
        cmd = self.object_command.currentText().split()
        target = shlex.split(self.object_target.text().strip()) if self.object_target.text().strip() else []
        self.run_git_command(cmd + target, callback=lambda r: self.advanced_output.setPlainText(r.output))

    def _command_changed(self) -> None:
        name = self.command_combo.currentData()
        spec: GitCommandSpec = self.command_catalog.get(name, GitCommandSpec(name=name or "", category=""))
        self.command_desc.setText(f"类别：{spec.category}\n说明：{spec.description or '本机 Git 动态命令；可在参数框中输入任意参数。'}")
        self.command_examples.clear()
        for example in spec.examples:
            self.command_examples.addItem(example)
        self._clear_option_checks()
        for opt in spec.common_options[:12]:
            cb = QCheckBox(opt)
            cb.stateChanged.connect(self.update_command_preview)
            self.options_layout.insertWidget(max(0, self.options_layout.count() - 1), cb)
            self._option_checks.append(cb)
        self.update_command_preview()

    def _clear_option_checks(self) -> None:
        for cb in self._option_checks:
            self.options_layout.removeWidget(cb)
            cb.deleteLater()
        self._option_checks.clear()

    def selected_advanced_args(self) -> List[str]:
        name = self.command_combo.currentData()
        args = [name]
        for cb in self._option_checks:
            if cb.isChecked():
                args.extend(shlex.split(cb.text()))
        text = self.command_args.text().strip()
        if text:
            args.extend(shlex.split(text))
        return args

    def update_command_preview(self) -> None:
        if self._suppress_preview:
            return
        try:
            args = self.selected_advanced_args()
            self.command_preview.setText("git " + " ".join(shlex.quote(a) for a in args))
        except ValueError as exc:
            self.command_preview.setText(f"参数解析错误：{exc}")

    def run_advanced_command(self) -> None:
        try:
            args = self.selected_advanced_args()
        except ValueError as exc:
            QMessageBox.warning(self, "参数解析错误", str(exc))
            return
        self.run_git_command(args, callback=lambda r: self.all_commands_output.setPlainText(r.output), timeout=600)

    def use_command_example(self, item: QListWidgetItem) -> None:
        text = item.text().strip()
        parts = shlex.split(text)
        if parts and parts[0] == "git":
            parts = parts[1:]
        if not parts:
            return
        name = parts[0]
        index = self.command_combo.findData(name)
        if index >= 0:
            self.command_combo.setCurrentIndex(index)
        self.command_args.setText(" ".join(shlex.quote(x) for x in parts[1:]))

    def open_selected_command_help(self) -> None:
        name = self.command_combo.currentData()
        if name:
            self.run_git_command(["help", name], callback=lambda r: self.all_commands_output.setPlainText(r.output), timeout=120, risk_check=False)

    def reload_command_catalog(self) -> None:
        self.command_catalog = build_command_catalog()
        current = self.command_combo.currentData()
        self.command_combo.clear()
        for name, spec in self.command_catalog.items():
            self.command_combo.addItem(f"{name}  [{spec.category}]", name)
        if current:
            idx = self.command_combo.findData(current)
            if idx >= 0:
                self.command_combo.setCurrentIndex(idx)
        self._command_changed()

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------
    def gitee_list_repos(self) -> None:
        token = self.gitee_token.text().strip()
        user = self.gitee_user.text().strip()
        if not token or not user:
            QMessageBox.warning(self, "缺少参数", "请输入 Gitee token 和用户名/组织。")
            return
        try:
            import requests

            url = f"https://gitee.com/api/v5/users/{user}/repos"
            resp = requests.get(url, params={"access_token": token, "per_page": 50}, timeout=20)
            data = resp.json()
            self.platform_output.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.platform_output.setPlainText(str(exc))

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def create_rescue_branch(self) -> None:
        name, ok = QInputDialog.getText(self, "Rescue Branch", "救援分支名：", text="rescue/head-1")
        if ok and name.strip():
            self.run_git_command(["switch", "-c", name.strip(), "HEAD@{1}"], callback=lambda _: self.refresh_all())

    def copy_last_command(self) -> None:
        text = self.command_log.toPlainText().splitlines()
        for line in reversed(text):
            if line.startswith("git ") or line.startswith("✓ git ") or line.startswith("✗ git "):
                QApplication.clipboard().setText(line.replace("✓ ", "").replace("✗ ", ""))
                return

    def _navigator_clicked(self, item: QTreeWidgetItem) -> None:
        text = item.text(0)
        mapping = {
            "Workspace": 0,
            "Changed files": 0,
            "Staged files": 0,
            "Untracked files": 0,
            "History": 1,
            "Current branch": 1,
            "All branches": 1,
            "Reflog": 6,
            "Bisect": 7,
            "Refs": 2,
            "Local branches": 2,
            "Remote branches": 2,
            "Tags": 4,
            "Worktrees": 6,
            "Remotes": 3,
            "origin": 3,
            "upstream": 3,
            "Collaboration": 8,
            "GitHub": 8,
            "Gitee": 8,
            "GitLab": 8,
            "Bitbucket": 8,
            "Pull Requests": 8,
            "Issues": 8,
            "Releases": 8,
            "CI": 8,
            "Advanced": 6,
            "Stash": 4,
            "Submodules": 6,
            "LFS": 6,
            "Hooks": 6,
            "Config": 6,
            "Objects": 6,
            "Maintenance": 6,
            "Raw Commands": 7,
        }
        if text in mapping:
            self.tabs.setCurrentIndex(mapping[text])

    def show_terminal_help(self) -> None:
        QMessageBox.information(
            self,
            "原生命令入口",
            "底部命令栏支持输入：\n"
            ":git status -sb\n"
            ":git cat-file -p HEAD\n"
            ":git update-ref refs/heads/test <hash>\n\n"
            "高风险命令会要求输入确认词。",
        )

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "快捷键",
            "F5 刷新\nCtrl+O 打开仓库\nEnter 在底部命令栏执行 Raw Git 命令\n"
            "常用 Git 快捷键可在各面板按钮和右键菜单中使用。",
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Git Terminal",
            "Git Terminal\n\n"
            "一个基于本机 git CLI 的 PyQt Git 管理终端。\n"
            "高频功能图形化，全部 Git 命令通过高级参数面板和 Raw Git Terminal 兜底。",
        )
