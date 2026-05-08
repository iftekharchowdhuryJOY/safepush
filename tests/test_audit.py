from __future__ import annotations

from safepush.audit import write_run_audit_event


def test_write_run_audit_event_for_all_phase3_events(tmp_path):
    log_path = tmp_path / "audit.log"
    events = ["blocked", "aborted", "dry_run", "executed", "override_used"]

    for event in events:
        write_run_audit_event(
            str(log_path),
            event=event,
            blocked=event in {"blocked", "aborted"},
            execute=event in {"executed", "override_used"},
            override=event == "override_used",
            reason="test reason" if event == "override_used" else None,
            branch="main",
            remote="origin",
            files=["src/app.py"],
            findings_summary={"secret_pattern": 1} if event != "executed" else {},
            commit_hashes=["abc123"] if event in {"executed", "override_used"} else [],
        )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(events)
    for event in events:
        assert any(f"event={event}" in line for line in lines)
