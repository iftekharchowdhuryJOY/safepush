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
