
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Severity = Literal["low", "medium", "high", "critical"]


@dataclass
class FileChange:
    path: str
    status: str  # A, M, D, ??


@dataclass
class ScanFinding:
    kind: str  # denylist_path, secret_pattern, pii_pattern, scanner_error
    path: str
    detail: str
    severity: Severity
    line_no: int | None = None


@dataclass
class ScanReport:
    findings: list[ScanFinding] = field(default_factory=list)
    scanned_files: int = 0
    blocked: bool = False