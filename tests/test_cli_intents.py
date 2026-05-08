from __future__ import annotations

from typer.testing import CliRunner

from safepush.cli import app
from safepush.config import AppConfig


runner = CliRunner()


class _Repo:
    pass


def test_status_shows_plain_english_state(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    monkeypatch.setattr(
        "safepush.cli.get_repo_state",
        lambda _repo, _remote: {
            "branch": "main",
            "tracking": "origin/main",
            "ahead": 1,
            "behind": 0,
            "staged": 2,
            "unstaged": 1,
            "untracked": 0,
            "conflicted": False,
            "operation": "normal",
            "remote_ok": True,
            "clean": False,
        },
    )
    monkeypatch.setattr("safepush.cli.detect_repository_issues", lambda _repo, _remote: [])

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "safepush status" in result.output
    assert "No blocking git issues detected." in result.output


def test_fix_shows_issue_recommendations(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    monkeypatch.setattr(
        "safepush.cli.detect_repository_issues",
        lambda _repo, _remote: ["NO_REMOTE", "NO_UPSTREAM"],
    )

    result = runner.invoke(app, ["fix"])
    assert result.exit_code == 1
    assert "safepush fix" in result.output
    assert "Add remote 'origin'" in result.output
    assert "Set tracking branch" in result.output


def test_push_intent_delegates_to_run(monkeypatch):
    seen: dict[str, object] = {}

    def _fake_run(execute: bool, override: bool, reason: str | None, audit_log: bool):
        seen["execute"] = execute
        seen["override"] = override
        seen["reason"] = reason
        seen["audit_log"] = audit_log

    monkeypatch.setattr("safepush.cli.run", _fake_run)
    result = runner.invoke(app, ["push", "--override", "--reason", "ok"])
    assert result.exit_code == 0
    assert seen["execute"] is True
    assert seen["override"] is True
    assert seen["reason"] == "ok"
    assert seen["audit_log"] is True


def test_push_dry_run_sets_execute_false(monkeypatch):
    seen: dict[str, object] = {}

    def _fake_run(execute: bool, override: bool, reason: str | None, audit_log: bool):
        seen["execute"] = execute

    monkeypatch.setattr("safepush.cli.run", _fake_run)
    result = runner.invoke(app, ["push", "--dry-run"])
    assert result.exit_code == 0
    assert seen["execute"] is False
