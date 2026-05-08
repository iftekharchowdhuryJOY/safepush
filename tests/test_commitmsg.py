from safepush.commitmsg import (
    generate_per_file_commit_message,
    group_changes_for_smart_mode,
    summarize_diff,
)
from safepush.models import FileChange


def test_summarize_diff_counts_hunks_and_lines():
    diff = """@@ -1,2 +1,4 @@
-def old_name():
+def new_name():
     pass
-x = 1
+x = 2
"""
    summary = summarize_diff(diff)
    assert "hunks=1" in summary
    assert "+2/-2" in summary
    assert "symbols: new_name" in summary


def test_per_file_message_uses_diff_summary():
    msg = generate_per_file_commit_message(
        FileChange(path="src/app.py", status="M"),
        diff_summary="hunks=2 +20/-3; symbols: build_plan",
    )
    assert "refactor(app): refine app behavior" in msg
    assert "hunks=2 +20/-3" in msg


def test_grouped_message_subject_mentions_key_files():
    from safepush.commitmsg import generate_grouped_commit_message

    msg = generate_grouped_commit_message(
        [
            FileChange(path="src/cli.py", status="M"),
            FileChange(path="src/planner.py", status="M"),
            FileChange(path="src/gitops.py", status="M"),
        ]
    )
    subject = msg.splitlines()[0]
    assert subject.startswith("refactor(cli):")
    assert "refine" in subject
    assert "CLI command flow" in subject


def test_smart_grouping_splits_by_category_and_topdir():
    changes = [
        FileChange(path="src/app.py", status="M"),
        FileChange(path="src/other.py", status="M"),
        FileChange(path="docs/readme.md", status="M"),
    ]
    grouped = group_changes_for_smart_mode(changes)
    assert len(grouped) == 2


def test_grouped_message_uses_fix_type_when_bug_keywords_present():
    from safepush.commitmsg import generate_grouped_commit_message

    msg = generate_grouped_commit_message(
        [FileChange(path="src/error_handler.py", status="M")],
        diff_summaries={"src/error_handler.py": "hunks=1 +2/-2; symbols: fix_crash"},
    )
    assert msg.splitlines()[0].startswith("fix(error_handler):")


def test_docs_scope_prefers_readme_token():
    from safepush.commitmsg import generate_grouped_commit_message

    msg = generate_grouped_commit_message([FileChange(path="README.md", status="M")])
    assert msg.splitlines()[0].startswith("docs(readme):")
