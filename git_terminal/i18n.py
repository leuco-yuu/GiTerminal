from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

LANGUAGE_MODES = {
    "zh": "中文",
    "en": "English",
    "default": "默认 / Default",
    "all": "中文 + English",
}

RESOURCE_PATH = Path(__file__).resolve().parent / "language_config.json"
USER_LANGUAGE_PATH = Path.home() / ".git_terminal" / "language_config.json"


_COMMON_ZH = {
    "Open": "打开", "Init": "初始化", "Clone...": "克隆...", "Folder": "打开文件夹",
    "Refresh": "刷新", "Repository": "仓库", "Changes": "更改", "History / Graph": "历史 / 图",
    "Branch": "分支", "Remote": "远程", "Advanced": "高级", "Platform": "平台", "User": "用户",
    "Status": "状态", "Diff": "差异", "Tags": "标签", "Stash": "贮藏", "Run": "运行", "Clear": "清空",
    "Copy": "复制", "Cancel": "取消", "OK": "确定", "Help": "帮助", "Settings": "设置",
    "Workspace": "工作区", "History": "历史", "Refs": "引用", "Remotes": "远程", "Collaboration": "协作",
    "File": "文件", "View": "视图", "Appearance": "外观", "Dark Mode": "深色模式", "Light Mode": "浅色模式",
    "Theme": "主题", "Accent": "配色", "Language": "语言", "Ready": "就绪", "Terminal": "终端",
    "Commit Only...": "仅提交...", "Add All + Commit...": "添加全部并提交...", "Add Selected": "添加选中",
    "Unstage All": "全部取消暂存", "Unstage Sel": "取消暂存选中", "Restore Sel": "恢复选中",
    "Clean": "清理", "Delete": "删除", "Switch": "切换", "New...": "新建...", "Log": "日志", "Show": "显示",
    "Checkout": "检出", "Cherry-pick": "拣选", "Revert": "回滚", "Push": "推送", "Pull": "拉取",
}

_COMMON_EN = {
    "打开本地仓库...": "Open Local Repository...", "创建/初始化本地仓库...": "Create / Initialize Local Repository...",
    "Clone 远程仓库...": "Clone Remote Repository...", "刷新全部": "Refresh All", "复制最后命令": "Copy Last Command",
    "文件": "File", "打开仓库文件夹": "Open Repository Folder", "创建 GitHub 远程仓库...": "Create GitHub Remote Repository...",
    "退出": "Exit", "仓库": "Repository", "打开 Raw Git 终端": "Open Raw Git Terminal", "查看配置": "Show Config",
    "设置 user.name...": "Set user.name...", "设置 user.email...": "Set user.email...", "刷新仓库状态": "Refresh Repository Status",
    "更改": "Changes", "git add -A / 添加全部": "git add -A / Add All", "分支": "Branch", "创建分支...": "Create Branch...",
    "切换分支...": "Switch Branch...", "分支列表": "Branch List", "远程": "Remote", "添加 Remote...": "Add Remote...",
    "设置 Remote URL...": "Set Remote URL...", "删除远程分支...": "Delete Remote Branch...", "标签": "Tags",
    "创建标签...": "Create Tag...", "高级": "Advanced", "全部 Git 命令": "All Git Commands", "视图": "View",
    "显示/隐藏左侧栏": "Show / Hide Left Sidebar", "显示/隐藏右侧栏": "Show / Hide Right Sidebar",
    "显示/隐藏底部栏": "Show / Hide Bottom Panel", "放大/缩小终端": "Maximize / Restore Terminal",
    "工作区": "Workspace", "历史": "History", "外观": "Appearance", "平台": "Platform", "帮助": "Help",
    "快捷键": "Shortcuts", "原生命令示例": "Native Command Examples", "关于 Git Terminal": "About Git Terminal",
    "深色模式": "Dark Mode", "浅色模式": "Light Mode", "配色": "Accent Color", "主题": "Theme", "语言": "Language",
    "显示左侧栏": "Show Left Sidebar", "显示右侧栏": "Show Right Sidebar", "显示底部栏": "Show Bottom Panel",
    "取消": "Cancel", "确定": "OK", "← 返回": "← Back", "提交目标": "Commit Target", "选择目录": "Choose Directory",
    "远程 URL": "Remote URL", "目标目录": "Target Directory", "远程仓库": "Remote Repository", "目标父目录": "Target Parent Directory",
    "创建分支": "Create Branch", "分支名：": "Branch name:", "切换分支": "Switch Branch", "要合并到当前分支的分支名：": "Branch to merge into current branch:",
    "当前分支 rebase 到：": "Rebase current branch onto:", "创建标签": "Create Tag", "提交历史": "Commit History",
    "列表": "List", "刷新图": "Refresh Graph", "适应视图": "Fit View", "有向图": "Directed Graph", "冲突": "Conflicts",
    "命令": "Command", "对象或参数": "Object or Arguments", "说明": "Description", "示例": "Examples", "参数": "Arguments", "预览": "Preview",
    "用户/组织": "User / Organization", "高级配置": "Advanced Configuration", "用户名 / 组织名": "Username / Organization",
    "收起底部终端": "Collapse Bottom Terminal", "输入任意命令，例如：git status -sb / python --version / dir / ls": "Enter any command, e.g. git status -sb / python --version / dir / ls",
}


def make_key(default_text: str, prefix: str = "ui") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", default_text.strip().lower()).strip("_")
    digest = hashlib.sha1(default_text.encode("utf-8")).hexdigest()[:8]
    if not cleaned or len(cleaned) < 2:
        cleaned = "text"
    return f"{prefix}.{cleaned[:42]}.{digest}"


def _guess_en(text: str) -> str:
    if text in _COMMON_EN:
        return _COMMON_EN[text]
    out = text
    for zh, en in sorted(_COMMON_EN.items(), key=lambda x: len(x[0]), reverse=True):
        out = out.replace(zh, en)
    return out


def _guess_zh(text: str) -> str:
    if text in _COMMON_ZH:
        return _COMMON_ZH[text]
    out = text
    for en, zh in sorted(_COMMON_ZH.items(), key=lambda x: len(x[0]), reverse=True):
        out = re.sub(rf"\b{re.escape(en)}\b", zh, out)
    return out


def make_entry(default_text: str) -> dict[str, str]:
    zh = _guess_zh(default_text)
    en = _guess_en(default_text)
    all_text = f"{zh} ({en})" if zh != en else default_text
    return {"default": default_text, "zh": zh, "en": en, "all": all_text}


def load_language_config() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}
    for path in (RESOURCE_PATH, USER_LANGUAGE_PATH):
        try:
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        if isinstance(value, dict):
                            data[key] = {str(k): str(v) for k, v in value.items()}
        except Exception:
            continue
    return data


def save_user_language_config(data: dict[str, dict[str, str]]) -> None:
    USER_LANGUAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USER_LANGUAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


class LanguageService:
    def __init__(self, mode: str = "default") -> None:
        self.mode = mode if mode in LANGUAGE_MODES else "default"
        self.data = load_language_config()
        self._dirty = False

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in LANGUAGE_MODES else "default"

    def ensure(self, key: str, default_text: str) -> None:
        if not default_text:
            return
        if key not in self.data:
            self.data[key] = make_entry(default_text)
            self._dirty = True
        else:
            entry = self.data[key]
            changed = False
            for k, v in make_entry(default_text).items():
                if k not in entry:
                    entry[k] = v
                    changed = True
            if changed:
                self._dirty = True

    def text(self, key: str, default_text: str = "") -> str:
        self.ensure(key, default_text)
        entry = self.data.get(key, {})
        return entry.get(self.mode) or entry.get("default") or default_text

    def flush(self) -> None:
        if self._dirty:
            save_user_language_config(self.data)
            self._dirty = False
