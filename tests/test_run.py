from safepush.config import AppConfig
from safepush.models import ScanFinding, ScanReport
from safepush.runner import (
    decide_execution_intent,
    evaluate_override,
    evaluate_safety_gate,
    validate_preflight,
)


def test_dry_run_default_requires_execute_flag():
    cfg = AppConfig()
    cfg.safety.dry_run_default = True

    intent = decide_execution_intent(execute_flag=False, cfg=cfg)
    assert intent.execute is False
    assert intent.dry_run is True


def test_execute_flag_overrides_dry_run_default():
    cfg = AppConfig()
    cfg.safety.dry_run_default = True

    intent = decide_execution_intent(execute_flag=True, cfg=cfg)
    assert intent.execute is True
    assert intent.dry_run is False


def test_override_allowed_for_policy_findings_with_reason():
    report = ScanReport(
        findings=[ScanFinding(kind="secret_pattern", path="app.py", detail="Generic API key", severity="critical")],
        scanned_files=1,
        blocked=True,
    )
    gate = evaluate_safety_gate(report)

    allowed, errors, used = evaluate_override(gate, allow_override_flag=True, override=True, reason="fixture has fake key")
    assert allowed is True
    assert errors == []
    assert used is True


def test_override_denied_for_non_overridable_findings():
    report = ScanReport(
        findings=[ScanFinding(kind="scanner_error", path="*", detail="I/O failure", severity="critical")],
        scanned_files=0,
        blocked=True,
    )
    gate = evaluate_safety_gate(report)

    allowed, errors, used = evaluate_override(gate, allow_override_flag=True, override=True, reason="force")
    assert allowed is False
    assert used is False
    assert any("non-overridable" in err for err in errors)


def test_override_requires_reason():
    report = ScanReport(
        findings=[ScanFinding(kind="denylist_path", path=".env", detail="denylist", severity="critical")],
        scanned_files=1,
        blocked=True,
    )
    gate = evaluate_safety_gate(report)

    allowed, errors, used = evaluate_override(gate, allow_override_flag=True, override=True, reason=" ")
    assert allowed is False
    assert used is False
    assert "Override requires --reason with explicit intent." in errors


def test_preflight_blocks_missing_remote_when_execute_push():
    ok, errors = validate_preflight(
        execute=True,
        push=True,
        has_remote=False,
        repo_detached_head=False,
    )
    assert ok is False
    assert "Push is enabled but configured remote is missing." in errors


def test_preflight_blocks_detached_head():
    ok, errors = validate_preflight(
        execute=True,
        push=False,
        has_remote=True,
        repo_detached_head=True,
    )
    assert ok is False
    assert "Cannot run from detached HEAD." in errors
