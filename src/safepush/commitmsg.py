from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from safepush.models import FileChange


def _category_for_path(path: str) -> str:
    p = path.lower()
    if p.endswith((".md", ".rst", ".txt")):
        return "docs"
    if "test" in p or p.endswith(("_test.py", ".spec.ts", ".test.ts", ".test.js")):
        return "test"
    if p.endswith((".yml", ".yaml", ".toml", ".json", ".ini")):
        return "config"
    if p.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java")):
        return "code"
    return "misc"


def _verb_for_statuses(statuses: list[str]) -> str:
    s = set(statuses)
    if s == {"??"}:
        return "add"
    if "??" in s and "M" in s:
        return "update"
    if s == {"M"}:
        return "update"
    if "D" in s:
        return "refactor"
    return "update"


def _scope_for_changes(changes: list[FileChange]) -> str:
    cats = Counter(_category_for_path(c.path) for c in changes)
    return cats.most_common(1)[0][0]


def _short_name(path: str) -> str:
    p = Path(path)
    name = p.stem if p.suffix else p.name
    if name.isdigit():
        return "misc-file"
    return name


def _subject_focus(changes: list[FileChange]) -> str:
    names = []
    seen: set[str] = set()
    for change in sorted(changes, key=lambda c: c.path):
        name = _short_name(change.path)
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    if not names:
        return "repository updates"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]}, {names[1]} (+{len(names) - 2} more)"


def _action_word(commit_type: str) -> str:
    return {
        "feat": "introduce",
        "fix": "fix",
        "refactor": "refine",
        "docs": "improve",
        "test": "improve",
        "chore": "update",
    }.get(commit_type, "improve")


def _topic_for_paths(changes: list[FileChange], scope: str) -> str:
    paths = [c.path.lower() for c in changes]
    keyword_topics = [
        ("cli.py", "CLI command flow"),
        ("gitops.py", "git state operations"),
        ("planner.py", "commit planning"),
        ("commitmsg.py", "commit message generation"),
        ("scanner.py", "safety scanning"),
        ("config.py", "configuration handling"),
        ("audit.py", "audit logging"),
        ("runner.py", "execution orchestration"),
        ("readme", "documentation"),
    ]
    for keyword, topic in keyword_topics:
        if any(keyword in path for path in paths):
            return topic
    if scope == "test":
        return "test coverage"
    if scope == "docs":
        return "documentation"
    if scope == "config":
        return "project configuration"
    if scope == "misc":
        return "repository housekeeping"
    return "core behavior"


def _scope_token_for_changes(changes: list[FileChange], scope: str) -> str:
    paths = [change.path for change in changes]
    lowered = [path.lower() for path in paths]

    if scope == "docs":
        if any(path.endswith("readme.md") for path in lowered):
            return "readme"
        return "docs"

    if scope == "test":
        stems: list[str] = []
        for path in paths:
            stem = Path(path).stem
            if stem.startswith("test_"):
                stem = stem[len("test_") :]
            elif stem.endswith("_test"):
                stem = stem[: -len("_test")]
            if stem:
                stems.append(stem)
        if stems:
            return stems[0].replace("-", "_")
        return "tests"

    if scope == "config":
        if any(path.endswith(".safepush.toml") for path in lowered):
            return "safepush"
        return "config"

    if scope == "misc":
        return "repo"

    for path in paths:
        p = Path(path)
        if p.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}:
            return p.stem.replace("-", "_")
    return scope


def _looks_like_fix(paths: list[str], diff_summaries: dict[str, str] | None = None) -> bool:
    haystacks = list(paths)
    if diff_summaries:
        haystacks.extend(diff_summaries.values())
    text = "\n".join(haystacks).lower()
    hints = ("fix", "bug", "error", "issue", "regress", "exception", "panic", "crash")
    return any(hint in text for hint in hints)


def _commit_type_for_changes(
    changes: list[FileChange],
    scope: str,
    diff_summaries: dict[str, str] | None = None,
) -> str:
    if scope == "docs":
        return "docs"
    if scope == "test":
        return "test"
    if scope in {"config", "misc"}:
        return "chore"

    statuses = [change.status for change in changes]
    status_set = set(statuses)
    paths = [change.path for change in changes]
    if "D" in status_set:
        return "refactor"
    if status_set == {"??"}:
        return "feat"
    if _looks_like_fix(paths, diff_summaries):
        return "fix"
    if "??" in status_set:
        return "feat"
    return "refactor"


def _extract_symbols(diff_text: str) -> list[str]:
    symbols: list[str] = []
    patterns = [
        r"^\+\s*def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\+\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\+\s*function\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    for line in diff_text.splitlines():
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                symbols.append(match.group(1))
                break
    seen: set[str] = set()
    out: list[str] = []
    for sym in symbols:
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out[:3]


def summarize_diff(diff_text: str) -> str:
    if not diff_text.strip():
        return "diff unavailable"
    added = 0
    removed = 0
    hunks = 0
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            hunks += 1
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    symbols = _extract_symbols(diff_text)
    symbol_hint = f"; symbols: {', '.join(symbols)}" if symbols else ""
    return f"hunks={hunks} +{added}/-{removed}{symbol_hint}"


def generate_grouped_commit_message(changes: list[FileChange], diff_summaries: dict[str, str] | None = None) -> str:
    if not changes:
        return "chore: no-op commit"

    scope = _scope_for_changes(changes)
    scope_token = _scope_token_for_changes(changes, scope)
    commit_type = _commit_type_for_changes(changes, scope, diff_summaries)
    action = _action_word(commit_type)
    topic = _topic_for_paths(changes, scope)
    summary = f"{action} {topic}"
    if scope == "test":
        summary = f"{action} {topic} for {_subject_focus(changes)}"
    paths = ", ".join(sorted(c.path for c in changes)[:3])
    diff_hint = ""
    if diff_summaries:
        sample_path = sorted(c.path for c in changes)[0]
        sample_summary = diff_summaries.get(sample_path, "")
        if sample_summary:
            diff_hint = f"\n\nsample diff ({sample_path}): {sample_summary}"
    detail = f"auto-generated by safepush deterministic planner; rationale: touched {len(changes)} file(s): {paths}{diff_hint}"

    return f"{commit_type}({scope_token}): {summary}\n\n{detail}"


def generate_per_file_commit_message(change: FileChange, diff_summary: str = "") -> str:
    scope = _category_for_path(change.path)
    scope_token = _scope_token_for_changes([change], scope)
    commit_type = _commit_type_for_changes([change], scope, {change.path: diff_summary} if diff_summary else None)
    name = Path(change.path).name
    action = _action_word(commit_type)
    if scope == "docs":
        summary = f"{action} documentation in {name}"
    elif scope == "test":
        summary = f"{action} tests in {name}"
    else:
        summary = f"{action} {Path(name).stem} behavior"
    detail = "auto-generated by safepush deterministic planner; rationale: focused single-file change"
    if diff_summary:
        detail += f"; {diff_summary}"
    return f"{commit_type}({scope_token}): {summary}\n\n{detail}"


def group_changes_for_smart_mode(changes: list[FileChange]) -> list[list[FileChange]]:
    grouped: dict[tuple[str, str], list[FileChange]] = {}
    for change in changes:
        category = _category_for_path(change.path)
        top_dir = change.path.split("/", 1)[0] if "/" in change.path else "root"
        grouped.setdefault((category, top_dir), []).append(change)
    ordered = sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
    return [sorted(group, key=lambda c: c.path) for _, group in ordered]