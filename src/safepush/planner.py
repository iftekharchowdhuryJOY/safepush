from __future__ import annotations

from dataclasses import dataclass, field

from safepush.commitmsg import generate_grouped_commit_message, generate_per_file_commit_message
from safepush.config import AppConfig
from safepush.models import FileChange, ScanReport


@dataclass
class PlannedCommit:
    files: list[str]
    message: str


@dataclass
class ExecutionPlan:
    commits: list[PlannedCommit] = field(default_factory=list)
    commit_mode: str = "grouped"
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)


def build_plan(changes: list[FileChange], report: ScanReport, cfg: AppConfig) -> ExecutionPlan:
    plan = ExecutionPlan(commit_mode=cfg.git.commit_mode)

    if report.blocked:
        plan.blocked = True
        plan.reasons.append("Safety scan blocked execution.")
        return plan

    sorted_changes = sorted(changes, key=lambda ch: ch.path)
    sorted_paths = [ch.path for ch in sorted_changes]
    if not sorted_paths:
        return plan

    mode = cfg.git.commit_mode
    if mode == "per_file":
        for change in sorted_changes:
            plan.commits.append(
                PlannedCommit(
                    files=[change.path],
                    message=generate_per_file_commit_message(change),
                )
            )
    else:
        plan.commits.append(
            PlannedCommit(
                files=sorted_paths,
                message=generate_grouped_commit_message(sorted_changes),
            )
        )

    return plan

