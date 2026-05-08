from __future__ import annotations

from dataclasses import dataclass, field

from safepush.commitmsg import (
    generate_grouped_commit_message,
    generate_per_file_commit_message,
    group_changes_for_smart_mode,
)
from safepush.config import AppConfig
from safepush.intelligence import generate_llm_commit_message
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


def _message_with_optional_llm(
    cfg: AppConfig,
    deterministic_message: str,
    *,
    prompt_kind: str,
    context: str,
) -> str:
    llm_message = generate_llm_commit_message(cfg, prompt_kind=prompt_kind, context=context)
    if llm_message:
        return llm_message
    return deterministic_message


def build_plan(
    changes: list[FileChange],
    report: ScanReport,
    cfg: AppConfig,
    diff_summaries: dict[str, str] | None = None,
) -> ExecutionPlan:
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
            diff_summary = (diff_summaries or {}).get(change.path, "")
            deterministic = generate_per_file_commit_message(change, diff_summary=diff_summary)
            plan.commits.append(
                PlannedCommit(
                    files=[change.path],
                    message=_message_with_optional_llm(
                        cfg,
                        deterministic,
                        prompt_kind="per_file",
                        context=f"path={change.path}\nstatus={change.status}\ndiff={diff_summary}",
                    ),
                )
            )
    elif mode == "smart":
        for group in group_changes_for_smart_mode(sorted_changes):
            files = [change.path for change in group]
            deterministic = generate_grouped_commit_message(group, diff_summaries=diff_summaries)
            plan.commits.append(
                PlannedCommit(
                    files=files,
                    message=_message_with_optional_llm(
                        cfg,
                        deterministic,
                        prompt_kind="smart_group",
                        context="\n".join(files),
                    ),
                )
            )
    else:
        deterministic = generate_grouped_commit_message(sorted_changes, diff_summaries=diff_summaries)
        plan.commits.append(
            PlannedCommit(
                files=sorted_paths,
                message=_message_with_optional_llm(
                    cfg,
                    deterministic,
                    prompt_kind="grouped",
                    context="\n".join(sorted_paths),
                ),
            )
        )

    return plan

