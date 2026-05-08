from __future__ import annotations

from dataclasses import dataclass, field

from safepush.config import AppConfig
from safepush.models import FileChange, ScanFinding, ScanReport
from safepush.planner import ExecutionPlan


OVERRIDABLE_FINDING_KINDS = {"denylist_path", "secret_pattern", "pii_pattern"}
NON_OVERRIDABLE_FINDING_KINDS = {"scanner_error"}


@dataclass
class SafetyGateDecision:
    blocked: bool
    overridable: bool
    reasons: list[str] = field(default_factory=list)
    blocked_findings: list[ScanFinding] = field(default_factory=list)


@dataclass
class ExecutionIntent:
    execute: bool
    dry_run: bool
    push: bool


def decide_execution_intent(execute_flag: bool, cfg: AppConfig) -> ExecutionIntent:
    execute = execute_flag or not cfg.safety.dry_run_default
    dry_run = not execute
    push = execute and cfg.git.push
    return ExecutionIntent(execute=execute, dry_run=dry_run, push=push)


def evaluate_safety_gate(report: ScanReport) -> SafetyGateDecision:
    if not report.blocked:
        return SafetyGateDecision(blocked=False, overridable=False)

    blocked_findings = [f for f in report.findings if f.severity in ("critical", "high")]
    if not blocked_findings:
        return SafetyGateDecision(
            blocked=True,
            overridable=False,
            reasons=["Scanner returned blocked state without actionable findings."],
            blocked_findings=[],
        )

    non_overridable = [f for f in blocked_findings if f.kind in NON_OVERRIDABLE_FINDING_KINDS]
    overridable = not non_overridable and all(f.kind in OVERRIDABLE_FINDING_KINDS for f in blocked_findings)

    reasons: list[str] = []
    if non_overridable:
        reasons.append("Safety block is non-overridable due to scanner/runtime failure findings.")
    elif not overridable:
        reasons.append("Safety block includes non-overridable finding types.")
    else:
        reasons.append("Safety scan blocked execution. Override is allowed for this run.")

    return SafetyGateDecision(
        blocked=True,
        overridable=overridable,
        reasons=reasons,
        blocked_findings=blocked_findings,
    )


def evaluate_override(
    gate: SafetyGateDecision,
    allow_override_flag: bool,
    override: bool,
    reason: str | None,
) -> tuple[bool, list[str], bool]:
    if not gate.blocked:
        return True, [], False

    if not override:
        return False, ["Safety scan blocked execution."], False

    if not allow_override_flag:
        return False, ["Overrides are disabled by configuration."], False

    if not gate.overridable:
        return False, gate.reasons or ["Safety block is non-overridable."], False

    cleaned_reason = (reason or "").strip()
    if not cleaned_reason:
        return False, ["Override requires --reason with explicit intent."], False

    return True, [], True


def validate_preflight(
    *,
    execute: bool,
    push: bool,
    has_remote: bool,
    repo_detached_head: bool,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if repo_detached_head:
        errors.append("Cannot run from detached HEAD.")
    if execute and push and not has_remote:
        errors.append("Push is enabled but configured remote is missing.")
    return len(errors) == 0, errors


def summarize_findings(findings: list[ScanFinding]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.kind] = summary.get(finding.kind, 0) + 1
    return summary


def summarize_plan(plan: ExecutionPlan) -> tuple[int, int]:
    commit_count = len(plan.commits)
    file_count = sum(len(commit.files) for commit in plan.commits)
    return commit_count, file_count


def normalize_changes(changes: list[FileChange]) -> list[FileChange]:
    seen: set[str] = set()
    out: list[FileChange] = []
    for change in sorted(changes, key=lambda c: c.path):
        if change.path in seen:
            continue
        seen.add(change.path)
        out.append(change)
    return out
