from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from git_terminal.core.runner import GitRunner


def git_available() -> bool:
    return shutil.which("git") is not None


pytestmark = pytest.mark.skipif(not git_available(), reason="git executable is required")


def configure_identity(runner: GitRunner) -> None:
    assert runner.run(["config", "user.name", "Git Terminal Test"]).ok
    assert runner.run(["config", "user.email", "git-terminal@example.test"]).ok


def test_invalid_working_directory_returns_error_without_crashing(tmp_path: Path) -> None:
    runner = GitRunner(tmp_path / "missing" / "repo")
    result = runner.run(["status"])
    assert not result.ok
    assert result.stderr or result.output


def test_core_git_workflow_branch_tag_stash_remote_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = GitRunner(repo)

    assert runner.run(["init"]).ok
    configure_identity(runner)

    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    assert runner.run(["add", "README.md"]).ok
    assert runner.run(["commit", "-m", "initial commit"]).ok
    head = runner.run(["rev-parse", "--short", "HEAD"])
    assert head.ok and head.stdout.strip()

    assert runner.run(["branch", "feature/test"]).ok
    assert runner.run(["switch", "feature/test"]).ok
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    assert runner.run(["add", "feature.txt"]).ok
    assert runner.run(["commit", "-m", "feature commit"]).ok
    assert runner.run(["switch", "master"]).ok or runner.run(["switch", "main"]).ok
    base_branch = runner.run(["branch", "--show-current"]).stdout.strip()
    assert base_branch
    assert runner.run(["merge", "feature/test"]).ok

    assert runner.run(["tag", "-a", "v0.0.1", "-m", "v0.0.1"]).ok
    assert "v0.0.1" in runner.run(["tag", "--list"]).stdout

    (repo / "scratch.txt").write_text("scratch\n", encoding="utf-8")
    assert runner.run(["stash", "push", "-u", "-m", "scratch stash"]).ok
    assert "scratch stash" in runner.run(["stash", "list"]).stdout
    assert runner.run(["stash", "pop"]).ok
    assert (repo / "scratch.txt").exists()
    assert runner.run(["add", "scratch.txt"]).ok
    assert runner.run(["commit", "-m", "restore scratch"]).ok

    remote = tmp_path / "remote.git"
    assert GitRunner(tmp_path).run(["init", "--bare", str(remote)]).ok
    assert runner.run(["remote", "add", "origin", str(remote)]).ok
    assert runner.run(["remote", "get-url", "--push", "origin"]).ok
    assert runner.run(["push", "-u", "origin", base_branch]).ok

    worktree_path = tmp_path / "repo-worktree"
    assert runner.run(["worktree", "add", "-b", "worktree/test", str(worktree_path), base_branch]).ok
    assert worktree_path.exists()
    assert runner.run(["worktree", "remove", str(worktree_path)]).ok

    assert runner.run(["cat-file", "-t", "HEAD"]).stdout.strip() == "commit"
    assert runner.run(["count-objects", "-vH"]).ok
    assert runner.run(["fsck", "--full"]).ok


def test_add_all_tracks_multiple_untracked_files_before_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo-multi-add"
    repo.mkdir()
    runner = GitRunner(repo)

    assert runner.run(["init"]).ok
    configure_identity(runner)

    nested = repo / "content" / "post" / "线性回归-20251202100805"
    nested.mkdir(parents=True)
    files = [
        repo / "test1.txt",
        nested / "新建 Markdown File.md",
        nested / "新建 Markdown File (2).md",
        nested / "新建 文本文档.txt",
    ]
    for index, path in enumerate(files):
        path.write_text(f"file {index}\n", encoding="utf-8")

    assert runner.run(["add", "-A"]).ok
    staged = runner.run(["-c", "core.quotepath=false", "status", "--porcelain"])
    assert staged.ok
    normalized_status = staged.stdout.replace("\\", "/")
    for path in files:
        assert str(path.relative_to(repo)).replace("\\", "/") in normalized_status

    commit = runner.run(["commit", "-m", "add multiple untracked files"])
    assert commit.ok, commit.output
    clean = runner.run(["status", "--porcelain"])
    assert clean.ok
    assert clean.stdout.strip() == ""
