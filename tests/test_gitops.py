from __future__ import annotations

from pathlib import Path

from git import Repo

from safepush.gitops import apply_execution_plan, changed_and_untracked
from safepush.planner import ExecutionPlan, PlannedCommit


def _init_repo(tmp_path: Path) -> Repo:
    repo = Repo.init(tmp_path)
    with repo.config_writer() as cfg:
        cfg.set_value("user", "name", "safepush-test")
        cfg.set_value("user", "email", "test@example.com")
    return repo


def test_changed_and_untracked_marks_deleted_files(tmp_path: Path):
    repo = _init_repo(tmp_path)
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello\n", encoding="utf-8")
    repo.git.add("sample.txt")
    repo.index.commit("init")

    file_path.unlink()
    changes = changed_and_untracked(repo)
    by_path = {c.path: c.status for c in changes}
    assert by_path["sample.txt"] == "D"


def test_apply_execution_plan_handles_deleted_file_paths(tmp_path: Path):
    repo = _init_repo(tmp_path)
    file_path = tmp_path / "old.txt"
    file_path.write_text("to be deleted\n", encoding="utf-8")
    repo.git.add("old.txt")
    repo.index.commit("init")

    file_path.unlink()
    plan = ExecutionPlan(
        commit_mode="grouped",
        commits=[PlannedCommit(files=["old.txt"], message="chore(repo): remove old file")],
    )

    hashes = apply_execution_plan(repo, plan, push=False, remote="origin", branch="main")
    assert len(hashes) == 1
    assert not file_path.exists()
    names = repo.git.show("--name-status", "--pretty=format:", "HEAD").splitlines()
    assert any(line.strip().startswith("D\told.txt") for line in names)
