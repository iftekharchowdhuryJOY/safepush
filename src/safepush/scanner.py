from __future__ import annotations

import re
from pathlib import Path
from pathspec import PathSpec
from safepush.config import AppConfig
from safepush.models import FileChange, ScanFinding, ScanReport


SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"(?i)aws_secret_access_key\s*[:=]\s*[\"']?[A-Za-z0-9/\+=]{40}[\"']?", "AWS Secret"),
    (r"(?i)api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']?", "Generic API key"),
    (r"(?i)token\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']?", "Generic token"),
    (r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----", "Private key"),
]

PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "US SSN"),
    (r"\b(?:\d[ -]*?){13,16}\b", "Potential card number"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "Email address"),
]


def _compile_patterns(patterns: list[tuple[str, str]]) -> list[tuple[re.Pattern, str]]:
    return [(re.compile(p), label) for p, label in patterns]


COMPILED_SECRET = _compile_patterns(SECRET_PATTERNS)
COMPILED_PII = _compile_patterns(PII_PATTERNS)


def scan_changes(changes: list[FileChange], cfg: AppConfig) -> ScanReport:
    report = ScanReport()
    deny_spec = PathSpec.from_lines("gitignore", cfg.safety.deny_globs)

    try:
        for ch in changes:
            p = Path(ch.path)
            report.scanned_files += 1

            if deny_spec.match_file(ch.path):
                report.findings.append(
                    ScanFinding(
                        kind="denylist_path",
                        path=ch.path,
                        detail="File matches denylist glob",
                        severity="critical",
                    )
                )
                continue

            if ch.status == "D":
                continue
            if not p.exists() or p.is_dir():
                continue

            text = p.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()

            if cfg.scanner.detect_secrets:
                for i, line in enumerate(lines, start=1):
                    for pattern, label in COMPILED_SECRET:
                        if pattern.search(line):
                            report.findings.append(
                                ScanFinding(
                                    kind="secret_pattern",
                                    path=ch.path,
                                    detail=label,
                                    severity="critical",
                                    line_no=i,
                                )
                            )

            if cfg.scanner.detect_pii:
                for i, line in enumerate(lines, start=1):
                    for pattern, label in COMPILED_PII:
                        if pattern.search(line):
                            sev = "medium" if label == "Email address" else "high"
                            report.findings.append(
                                ScanFinding(
                                    kind="pii_pattern",
                                    path=ch.path,
                                    detail=label,
                                    severity=sev,
                                    line_no=i,
                                )
                            )

    except Exception as exc:
        report.findings.append(
            ScanFinding(
                kind="scanner_error",
                path="*",
                detail=f"Scanner failure: {exc}",
                severity="critical",
            )
        )
        if cfg.scanner.fail_closed:
            report.blocked = True
            return report

    report.blocked = any(f.severity in ("critical", "high") for f in report.findings)
    return report
