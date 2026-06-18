from git_terminal.core.models import RiskLevel
from git_terminal.core.safety import classify_git_command


def test_reset_hard_high_risk():
    assert classify_git_command(["reset", "--hard", "HEAD~1"]).level == RiskLevel.HIGH


def test_force_push_high_risk():
    assert classify_git_command("git push --force-with-lease origin main").level == RiskLevel.HIGH


def test_status_low_risk():
    assert classify_git_command(["status", "-sb"]).level == RiskLevel.LOW


def test_commit_medium_risk():
    assert classify_git_command(["commit", "-m", "msg"]).level == RiskLevel.MEDIUM
