from __future__ import annotations

from pathlib import Path
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
from git.exc import GitCommandError
from safepush.planner import ExecutionPlan
from safepush.models import FileChange


def get_repo(path: Path | None = None) -> Repo:
    try:
        return Repo(path or Path.cwd(), search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise RuntimeError("Not inside a git repository.") from exc


def changed_and_untracked(repo: Repo) -> list[FileChange]:
    out: list[FileChange] = []

    for item in repo.index.diff(None):
        out.append(FileChange(path=item.a_path, status="M"))

    for untracked in repo.untracked_files:
        out.append(FileChange(path=untracked, status="??"))

    # de-dupe in case of odd overlaps
    seen = set()
    deduped: list[FileChange] = []
    for c in out:
        if c.path not in seen:
            seen.add(c.path)
            deduped.append(c)
    return deduped


def branch_name(repo: Repo) -> str:
    return repo.active_branch.name


def has_remote(repo: Repo, name: str) -> bool:
    return any(r.name == name for r in repo.remotes)


def get_operation_state(repo: Repo) -> str:
    git_dir = Path(repo.git_dir)
    if (git_dir / "MERGE_HEAD").exists():
        return "merge"
    if (git_dir / "CHERRY_PICK_HEAD").exists():
        return "cherry-pick"
    if (git_dir / "REVERT_HEAD").exists():
        return "revert"
    if (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists():
        return "rebase"
    if (git_dir / "BISECT_LOG").exists():
        return "bisect"
    return "normal"


def _ahead_behind(repo: Repo, tracking_ref: str) -> tuple[int, int]:
    try:
        out = repo.git.rev_list("--left-right", "--count", f"{tracking_ref}...HEAD")
        behind, ahead = (int(part) for part in out.strip().split())
        return ahead, behind
    except Exception:
        return 0, 0


def get_repo_state(repo: Repo, remote_name: str) -> dict[str, object]:
    branch = "DETACHED" if repo.head.is_detached else repo.active_branch.name
    tracking = ""
    ahead = 0
    behind = 0
    if not repo.head.is_detached:
        tracking_branch = repo.active_branch.tracking_branch()
        if tracking_branch is not None:
            tracking = str(tracking_branch)
            ahead, behind = _ahead_behind(repo, tracking)

    try:
        staged = len(repo.index.diff("HEAD"))
    except Exception:
        staged = len(repo.index.diff(None))
    unstaged = len(repo.index.diff(None))
    untracked = len(repo.untracked_files)
    conflicted = bool(repo.index.unmerged_blobs())
    operation = get_operation_state(repo)
    remote_ok = has_remote(repo, remote_name)
    clean = staged == 0 and unstaged == 0 and untracked == 0 and not conflicted
    return {
        "branch": branch,
        "tracking": tracking,
        "ahead": ahead,
        "behind": behind,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "conflicted": conflicted,
        "operation": operation,
        "remote_ok": remote_ok,
        "clean": clean,
    }


def detect_repository_issues(repo: Repo, remote_name: str) -> list[str]:
    state = get_repo_state(repo, remote_name)
    issues: list[str] = []
    if state["branch"] == "DETACHED":
        issues.append("DETACHED_HEAD")
    if state["operation"] != "normal":
        issues.append(f"OPERATION_{str(state['operation']).upper()}")
    if state["conflicted"]:
        issues.append("UNMERGED_PATHS")
    if not state["remote_ok"]:
        issues.append("NO_REMOTE")
    if state["branch"] != "DETACHED" and not state["tracking"]:
        issues.append("NO_UPSTREAM")
    if (Path(repo.git_dir) / "index.lock").exists():
        issues.append("INDEX_LOCK")
    return issues


def resolve_push_target(repo: Repo, remote_name: str, configured_branch: str = "") -> tuple[str, str]:
    branch = configured_branch
    if not branch:
        if repo.head.is_detached:
            raise RuntimeError("Cannot determine current branch (detached HEAD).")
        branch = repo.active_branch.name
    return remote_name, branch


def preview_git_actions(plan: ExecutionPlan, push: bool, remote: str, branch: str) -> list[str]:
    actions: list[str] = []
    for commit in plan.commits:
        quoted_files = " ".join(repr(path) for path in commit.files)
        subject = commit.message.splitlines()[0]
        actions.append(f"git add {quoted_files}")
        actions.append(f"git commit -m {subject!r}")
    if push:
        actions.append(f"git push {remote} {branch}")
    return actions


def apply_execution_plan(
    repo: Repo,
    plan: ExecutionPlan,
    push: bool,
    remote: str,
    branch: str,
) -> list[str]:
    commit_hashes: list[str] = []
    for commit in plan.commits:
        if not commit.files:
            continue
        repo.index.add(commit.files)
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            continue
        new_commit = repo.index.commit(commit.message)
        commit_hashes.append(new_commit.hexsha)

    if push:
        if not has_remote(repo, remote):
            raise RuntimeError(f"Remote '{remote}' is missing.")
        try:
            repo.remotes[remote].push(branch)
        except GitCommandError as exc:
            raise RuntimeError(f"Failed to push to {remote}/{branch}: {exc}") from exc

    return commit_hashes
