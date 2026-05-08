from __future__ import annotations

from pathlib import Path
from git import Repo, InvalidGitRepositoryError, NoSuchPathError
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
