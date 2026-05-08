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


def test_fix_apply_sets_upstream_and_resolves(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    states = [["NO_UPSTREAM"], []]

    def _detect(_repo, _remote):
        return states.pop(0)

    monkeypatch.setattr("safepush.cli.detect_repository_issues", _detect)
    monkeypatch.setattr("safepush.cli.set_upstream_to_remote_branch", lambda _repo, _remote: "origin/main")

    result = runner.invoke(app, ["fix", "--apply", "--yes"])
    assert result.exit_code == 0
    assert "set upstream to origin/main" in result.output
    assert "All detected issues resolved." in result.output


def test_fix_apply_leaves_manual_issues_unresolved(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    monkeypatch.setattr("safepush.cli.detect_repository_issues", lambda _repo, _remote: ["NO_REMOTE"])

    result = runner.invoke(app, ["fix", "--apply", "--yes"])
    assert result.exit_code == 1
    assert "remote URL required (--remote-url)" in result.output
    assert "Some issues remain unresolved." in result.output


def test_fix_apply_no_remote_requires_remote_url(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    monkeypatch.setattr("safepush.cli.detect_repository_issues", lambda _repo, _remote: ["NO_REMOTE"])

    result = runner.invoke(app, ["fix", "--apply", "--yes"])
    assert result.exit_code == 1
    assert "remote URL required (--remote-url)" in result.output


def test_fix_apply_configures_no_remote_with_remote_url(monkeypatch):
    cfg = AppConfig()
    monkeypatch.setattr("safepush.cli._load_cfg_or_exit", lambda: cfg)
    monkeypatch.setattr("safepush.cli.get_repo", lambda: _Repo())
    states = [["NO_REMOTE"], []]

    def _detect(_repo, _remote):
        return states.pop(0)

    seen: dict[str, object] = {}

    def _add_remote(_repo, remote_name: str, remote_url: str):
        seen["remote_name"] = remote_name
        seen["remote_url"] = remote_url

    monkeypatch.setattr("safepush.cli.detect_repository_issues", _detect)
    monkeypatch.setattr("safepush.cli.add_or_update_remote", _add_remote)

    result = runner.invoke(
        app,
        ["fix", "--apply", "--yes", "--remote-url", "https://github.com/example/safepush.git"],
    )
    assert result.exit_code == 0
    assert seen["remote_name"] == "origin"
    assert seen["remote_url"] == "https://github.com/example/safepush.git"
    assert "configured remote 'origin'" in result.output


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


def test_preview_intent_always_sets_execute_false(monkeypatch):
    seen: dict[str, object] = {}

    def _fake_run(execute: bool, override: bool, reason: str | None, audit_log: bool):
        seen["execute"] = execute
        seen["override"] = override
        seen["reason"] = reason
        seen["audit_log"] = audit_log

    monkeypatch.setattr("safepush.cli.run", _fake_run)
    result = runner.invoke(app, ["preview", "--override", "--reason", "fixture"])
    assert result.exit_code == 0
    assert seen["execute"] is False
    assert seen["override"] is True
    assert seen["reason"] == "fixture"
