from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from safepush.models import ScanReport


def write_audit_log(path: str, report: ScanReport) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    p = Path(path)
    lines = [f"[{ts}] blocked={report.blocked} scanned_files={report.scanned_files} findings={len(report.findings)}"]
    for f in report.findings:
        loc = f"{f.path}:{f.line_no}" if f.line_no else f.path
        lines.append(f"  - {f.severity} {f.kind} {loc} :: {f.detail}")
    with p.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_run_audit_event(
    path: str,
    *,
    event: str,
    blocked: bool,
    execute: bool,
    override: bool,
    reason: str | None,
    branch: str,
    remote: str,
    files: list[str],
    findings_summary: dict[str, int],
    commit_hashes: list[str],
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    p = Path(path)
    mode = "execute" if execute else "dry_run"
    reason_text = (reason or "").strip() or "-"
    files_text = ",".join(files) if files else "-"
    findings_text = ",".join(f"{kind}:{count}" for kind, count in sorted(findings_summary.items())) or "-"
    commits_text = ",".join(commit_hashes) if commit_hashes else "-"
    line = (
        f"[{ts}] event={event} blocked={blocked} mode={mode} override={override} "
        f"branch={branch} remote={remote} files={files_text} findings={findings_text} "
        f"reason={reason_text!r} commits={commits_text}"
    )
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
