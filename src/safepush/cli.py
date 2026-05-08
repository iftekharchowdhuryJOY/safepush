from __future__ import annotations

from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from safepush.audit import write_audit_log, write_run_audit_event
from safepush.config import DEFAULT_CONFIG_PATH, init_default_config, load_config
from safepush.gitops import (
    add_or_update_remote,
    apply_execution_plan,
    build_diff_summaries,
    changed_and_untracked,
    detect_repository_issues,
    get_repo,
    get_repo_state,
    has_remote,
    preview_git_actions,
    resolve_push_target,
    set_upstream_to_remote_branch,
)
from safepush.models import ScanReport
from safepush.planner import build_plan
from safepush.runner import (
    decide_execution_intent,
    evaluate_override,
    evaluate_safety_gate,
    normalize_changes,
    summarize_findings,
    validate_preflight,
)
from safepush.scanner import scan_changes

app = typer.Typer(help="Safe git automation CLI")
config_app = typer.Typer(help="Config operations")
app.add_typer(config_app, name="config")
console = Console()


def _load_cfg_or_exit():
    try:
        return load_config()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)


def _render_scan_report(report: ScanReport) -> None:
    table = Table(title="Scan report")
    table.add_column("Severity")
    table.add_column("Kind")
    table.add_column("Path")
    table.add_column("Detail")
    for finding in report.findings:
        detail = finding.detail + (f" (line {finding.line_no})" if finding.line_no else "")
        table.add_row(finding.severity, finding.kind, finding.path, detail)
    if report.findings:
        console.print(table)
    else:
        console.print("[green]No findings.[/green]")
    console.print(f"Scanned files: {report.scanned_files}")
    console.print(f"Blocked: {'YES' if report.blocked else 'NO'}")


def _render_plan(execution_plan) -> None:
    table = Table(title=f"Commit plan ({execution_plan.commit_mode})")
    table.add_column("Commit #")
    table.add_column("Files")
    table.add_column("Message (subject)")
    for i, commit in enumerate(execution_plan.commits, start=1):
        subject = commit.message.splitlines()[0]
        table.add_row(str(i), str(len(commit.files)), subject)
    console.print(table)


def _write_run_event(
    *,
    cfg,
    event: str,
    blocked: bool,
    execute: bool,
    override: bool,
    reason: str | None,
    branch: str,
    remote: str,
    files: list[str],
    report,
    commit_hashes: list[str] | None = None,
) -> None:
    write_run_audit_event(
        cfg.audit_log_path,
        event=event,
        blocked=blocked,
        execute=execute,
        override=override,
        reason=reason,
        branch=branch,
        remote=remote,
        files=files,
        findings_summary=summarize_findings(report.findings),
        commit_hashes=commit_hashes or [],
    )


def _render_repo_state(state: dict[str, object], remote_name: str) -> None:
    table = Table(title="safepush status")
    table.add_column("Check")
    table.add_column("Value")
    table.add_row("Branch", str(state["branch"]))
    table.add_row("Tracking", str(state["tracking"] or "none"))
    table.add_row("Ahead / Behind", f"{state['ahead']} / {state['behind']}")
    table.add_row("Staged", str(state["staged"]))
    table.add_row("Unstaged", str(state["unstaged"]))
    table.add_row("Untracked", str(state["untracked"]))
    table.add_row("Conflicts", "YES" if state["conflicted"] else "NO")
    table.add_row("Operation", str(state["operation"]))
    table.add_row(f"Remote '{remote_name}'", "OK" if state["remote_ok"] else "MISSING")
    table.add_row("Clean tree", "YES" if state["clean"] else "NO")
    console.print(table)


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        run_interactive()


@app.command()
def doctor():
    """Validate git/auth/config readiness."""
    cfg = _load_cfg_or_exit()
    ok = True

    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    branch = repo.active_branch.name if not repo.head.is_detached else "DETACHED"
    remote_ok = has_remote(repo, cfg.git.remote)

    table = Table(title="safepush doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_row("Git repository", "OK")
    table.add_row("Current branch", branch)
    table.add_row(f"Remote '{cfg.git.remote}'", "OK" if remote_ok else "MISSING")
    table.add_row("Config file", "FOUND" if DEFAULT_CONFIG_PATH.exists() else "MISSING")
    console.print(table)

    if not remote_ok:
        ok = False
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def status():
    """Show plain-English git state and blockers."""
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    state = get_repo_state(repo, cfg.git.remote)
    _render_repo_state(state, cfg.git.remote)

    issues = detect_repository_issues(repo, cfg.git.remote)
    if issues:
        console.print("\n[yellow]Detected blockers:[/yellow]")
        for issue in issues:
            console.print(f"- {issue}")
    else:
        console.print("\n[green]No blocking git issues detected.[/green]")


@app.command()
def scan(audit_log: bool = typer.Option(True, "--audit-log/--no-audit-log")):
    """Show risky files/secrets."""
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    changes = changed_and_untracked(repo)

    if not changes:
        console.print("[green]No changed or untracked files.[/green]")
        raise typer.Exit()

    report = scan_changes(changes, cfg)
    _render_scan_report(report)

    if audit_log:
        write_audit_log(cfg.audit_log_path, report)

    if report.blocked:
        raise typer.Exit(code=3)


@config_app.command("init")
def config_init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
    path: Path = typer.Option(DEFAULT_CONFIG_PATH, "--path", help="Config path"),
):
    """Create config file."""
    try:
        out = init_default_config(path=path, force=force)
        console.print(f"[green]Created config at {out}[/green]")
    except FileExistsError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=1)
@app.command()
def plan():
    """Show commit plan/messages before writing."""
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    changes = changed_and_untracked(repo)
    if not changes:
        console.print("[yellow]No changed or untracked files.[/yellow]")
        raise typer.Exit(code=1)

    report = scan_changes(changes, cfg)
    diff_summaries = build_diff_summaries(repo, changes)
    execution_plan = build_plan(changes, report, cfg, diff_summaries=diff_summaries)

    if execution_plan.blocked:
        console.print("[red]Plan blocked.[/red]")
        for reason in execution_plan.reasons:
            console.print(f"- {reason}")
        raise typer.Exit(code=3)

    _render_plan(execution_plan)

    for i, c in enumerate(execution_plan.commits, start=1):
        console.print(f"\n[bold]Commit {i} full message:[/bold]\n{c.message}")
        for f in c.files:
            console.print(f"  - {f}")


@app.command()
def run(
    execute: bool = typer.Option(False, "--execute", help="Execute commit/push. Without this flag, safepush dry-runs by default."),
    override: bool = typer.Option(False, "--override", help="Override blocked safety findings for this run only."),
    reason: str | None = typer.Option(None, "--reason", help="Required with --override. Explain explicit risk intent."),
    audit_log: bool = typer.Option(True, "--audit-log/--no-audit-log"),
):
    """Plan + optionally execute commit/push with safety gates."""
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    branch_name = repo.active_branch.name if not repo.head.is_detached else "DETACHED"
    changes = normalize_changes(changed_and_untracked(repo))
    if not changes:
        console.print("[green]No changed or untracked files.[/green]")
        raise typer.Exit()

    report = scan_changes(changes, cfg)
    _render_scan_report(report)
    gate = evaluate_safety_gate(report)

    intent = decide_execution_intent(execute, cfg)
    remote_ok = has_remote(repo, cfg.git.remote)
    preflight_ok, preflight_errors = validate_preflight(
        execute=intent.execute,
        push=intent.push,
        has_remote=remote_ok,
        repo_detached_head=repo.head.is_detached,
    )
    if not preflight_ok:
        for err in preflight_errors:
            console.print(f"[red]{err}[/red]")
        if audit_log:
            _write_run_event(
                cfg=cfg,
                event="blocked",
                blocked=True,
                execute=intent.execute,
                override=override,
                reason=reason,
                branch=branch_name,
                remote=cfg.git.remote,
                files=[change.path for change in changes],
                report=report,
            )
        raise typer.Exit(code=2)

    allowed, errors, override_used = evaluate_override(gate, cfg.safety.allow_override_flag, override, reason)
    if not allowed:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        if audit_log:
            _write_run_event(
                cfg=cfg,
                event="blocked",
                blocked=True,
                execute=intent.execute,
                override=override,
                reason=reason,
                branch=branch_name,
                remote=cfg.git.remote,
                files=[change.path for change in changes],
                report=report,
            )
        raise typer.Exit(code=3)

    diff_summaries = build_diff_summaries(repo, changes)
    execution_plan = build_plan(changes, report, cfg, diff_summaries=diff_summaries)
    _render_plan(execution_plan)

    remote, push_branch = resolve_push_target(repo, cfg.git.remote, cfg.git.branch)
    if intent.dry_run:
        actions = preview_git_actions(execution_plan, intent.push, remote, push_branch)
        console.print("\n[bold]Dry-run preview[/bold]")
        for action in actions:
            console.print(f"- {action}")
        if audit_log:
            _write_run_event(
                cfg=cfg,
                event="dry_run",
                blocked=report.blocked,
                execute=False,
                override=override_used,
                reason=reason,
                branch=push_branch,
                remote=remote,
                files=[change.path for change in changes],
                report=report,
            )
        raise typer.Exit()

    commit_hashes = apply_execution_plan(repo, execution_plan, intent.push, remote, push_branch)
    console.print(f"[green]Created {len(commit_hashes)} commit(s).[/green]")
    for commit_hash in commit_hashes:
        console.print(f"- {commit_hash}")
    if intent.push:
        console.print(f"[green]Pushed to {remote}/{push_branch}[/green]")

    if audit_log:
        _write_run_event(
            cfg=cfg,
            event="override_used" if override_used else "executed",
            blocked=report.blocked,
            execute=True,
            override=override_used,
            reason=reason,
            branch=push_branch,
            remote=remote,
            files=[change.path for change in changes],
            report=report,
            commit_hashes=commit_hashes,
        )


@app.command()
def push(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview push flow without writing commits."),
    override: bool = typer.Option(False, "--override", help="Override blocked safety findings for this run only."),
    reason: str | None = typer.Option(None, "--reason", help="Required with --override. Explain explicit risk intent."),
    audit_log: bool = typer.Option(True, "--audit-log/--no-audit-log"),
):
    """Intent command: stage, commit, and push safely."""
    run(execute=not dry_run, override=override, reason=reason, audit_log=audit_log)


@app.command()
def preview(
    override: bool = typer.Option(False, "--override", help="Override blocked safety findings for this run only."),
    reason: str | None = typer.Option(None, "--reason", help="Required with --override. Explain explicit risk intent."),
    audit_log: bool = typer.Option(True, "--audit-log/--no-audit-log"),
):
    """Intent command: preview safe stage/commit/push plan without writes."""
    push(dry_run=True, override=override, reason=reason, audit_log=audit_log)


@app.command()
def fix(
    apply: bool = typer.Option(False, "--apply", help="Apply safe remediations for known issues."),
    yes: bool = typer.Option(False, "--yes", help="Apply without interactive confirmations."),
    remote_url: str | None = typer.Option(
        None,
        "--remote-url",
        help="Remote URL used to auto-remediate NO_REMOTE when applying fixes.",
    ),
):
    """Diagnose current git blockers and optionally apply safe remediations."""
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    issues = detect_repository_issues(repo, cfg.git.remote)
    if not issues:
        console.print("[green]No blocking git issues detected.[/green]")
        raise typer.Exit()

    recommendations = {
        "DETACHED_HEAD": "Switch/create a branch before continuing (e.g. git switch -c <branch>).",
        "UNMERGED_PATHS": "Resolve conflict markers, then git add files and continue/commit.",
        "NO_REMOTE": f"Add remote '{cfg.git.remote}' (git remote add {cfg.git.remote} <url>).",
        "NO_UPSTREAM": "Set tracking branch (git branch --set-upstream-to <remote>/<branch> <branch>).",
        "INDEX_LOCK": "A lock file exists; ensure no git process is running, then remove .git/index.lock if safe.",
        "OPERATION_MERGE": "Finish merge (git merge --continue) or abort (git merge --abort).",
        "OPERATION_REBASE": "Finish rebase (git rebase --continue) or abort (git rebase --abort).",
        "OPERATION_CHERRY-PICK": "Finish cherry-pick (git cherry-pick --continue) or abort (git cherry-pick --abort).",
        "OPERATION_REVERT": "Finish revert (git revert --continue) or abort (git revert --abort).",
        "OPERATION_BISECT": "Finish bisect before push (git bisect reset).",
    }

    table = Table(title="safepush fix")
    table.add_column("Issue")
    table.add_column("Recommended action")
    for issue in issues:
        table.add_row(issue, recommendations.get(issue, "Review git state and resolve manually."))
    console.print(table)

    if not apply:
        raise typer.Exit(code=1)

    # Safe, deterministic remediations only.
    apply_results: list[str] = []
    for issue in issues:
        if issue == "NO_REMOTE":
            if not remote_url:
                apply_results.append("NO_REMOTE: remote URL required (--remote-url) for auto-apply")
                continue
            should_apply = yes or typer.confirm(f"Set remote '{cfg.git.remote}' to '{remote_url}'?", default=True)
            if not should_apply:
                apply_results.append("NO_REMOTE: skipped by user")
                continue
            try:
                add_or_update_remote(repo, cfg.git.remote, remote_url)
                apply_results.append(f"NO_REMOTE: configured remote '{cfg.git.remote}'")
            except RuntimeError as exc:
                apply_results.append(f"NO_REMOTE: failed ({exc})")
            continue

        if issue == "NO_UPSTREAM":
            should_apply = yes or typer.confirm("Apply fix for NO_UPSTREAM now?", default=True)
            if not should_apply:
                apply_results.append("NO_UPSTREAM: skipped by user")
                continue
            try:
                target = set_upstream_to_remote_branch(repo, cfg.git.remote)
                apply_results.append(f"NO_UPSTREAM: set upstream to {target}")
            except RuntimeError as exc:
                apply_results.append(f"NO_UPSTREAM: failed ({exc})")
        else:
            apply_results.append(f"{issue}: manual action required")

    result_table = Table(title="fix apply results")
    result_table.add_column("Result")
    for line in apply_results:
        result_table.add_row(line)
    console.print(result_table)

    remaining = detect_repository_issues(repo, cfg.git.remote)
    if remaining:
        console.print("[yellow]Some issues remain unresolved.[/yellow]")
        raise typer.Exit(code=1)

    console.print("[green]All detected issues resolved.[/green]")


def run_interactive():
    cfg = _load_cfg_or_exit()
    try:
        repo = get_repo()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)

    branch_name = repo.active_branch.name if not repo.head.is_detached else "DETACHED"
    remote_ok = has_remote(repo, cfg.git.remote)
    preflight_table = Table(title="Interactive preflight")
    preflight_table.add_column("Check")
    preflight_table.add_column("Status")
    preflight_table.add_row("Git repository", "OK")
    preflight_table.add_row("Current branch", branch_name)
    preflight_table.add_row(f"Remote '{cfg.git.remote}'", "OK" if remote_ok else "MISSING")
    preflight_table.add_row("Config file", "FOUND" if DEFAULT_CONFIG_PATH.exists() else "MISSING")
    console.print(preflight_table)

    changes = normalize_changes(changed_and_untracked(repo))
    if not changes:
        console.print("[green]No changed or untracked files.[/green]")
        raise typer.Exit()

    report = scan_changes(changes, cfg)
    _render_scan_report(report)
    gate = evaluate_safety_gate(report)
    override_used = False
    reason: str | None = None

    if gate.blocked:
        if gate.overridable and cfg.safety.allow_override_flag:
            should_override = typer.confirm("Scan blocked. Override once for this run?", default=False)
            if not should_override:
                _write_run_event(
                    cfg=cfg,
                    event="aborted",
                    blocked=True,
                    execute=False,
                    override=False,
                    reason=None,
                    branch=branch_name,
                    remote=cfg.git.remote,
                    files=[change.path for change in changes],
                    report=report,
                )
                raise typer.Exit(code=3)
            reason = typer.prompt("Enter override reason")
            if not typer.confirm("Confirm override with this reason?", default=False):
                _write_run_event(
                    cfg=cfg,
                    event="aborted",
                    blocked=True,
                    execute=False,
                    override=False,
                    reason=reason,
                    branch=branch_name,
                    remote=cfg.git.remote,
                    files=[change.path for change in changes],
                    report=report,
                )
                raise typer.Exit(code=3)
            override_used = True
        else:
            for err in gate.reasons:
                console.print(f"[red]{err}[/red]")
            _write_run_event(
                cfg=cfg,
                event="blocked",
                blocked=True,
                execute=False,
                override=False,
                reason=None,
                branch=branch_name,
                remote=cfg.git.remote,
                files=[change.path for change in changes],
                report=report,
            )
            raise typer.Exit(code=3)

    diff_summaries = build_diff_summaries(repo, changes)
    execution_plan = build_plan(changes, report, cfg, diff_summaries=diff_summaries)
    _render_plan(execution_plan)
    execute_now = typer.confirm("Execute commit+push now?", default=not cfg.safety.dry_run_default)
    intent = decide_execution_intent(execute_now, cfg)
    preflight_ok, preflight_errors = validate_preflight(
        execute=intent.execute,
        push=intent.push,
        has_remote=remote_ok,
        repo_detached_head=repo.head.is_detached,
    )
    if not preflight_ok:
        for err in preflight_errors:
            console.print(f"[red]{err}[/red]")
        _write_run_event(
            cfg=cfg,
            event="blocked",
            blocked=True,
            execute=intent.execute,
            override=override_used,
            reason=reason,
            branch=branch_name,
            remote=cfg.git.remote,
            files=[change.path for change in changes],
            report=report,
        )
        raise typer.Exit(code=2)

    remote, push_branch = resolve_push_target(repo, cfg.git.remote, cfg.git.branch)
    if intent.dry_run:
        actions = preview_git_actions(execution_plan, intent.push, remote, push_branch)
        console.print("\n[bold]Dry-run preview[/bold]")
        for action in actions:
            console.print(f"- {action}")
        _write_run_event(
            cfg=cfg,
            event="dry_run",
            blocked=report.blocked,
            execute=False,
            override=override_used,
            reason=reason,
            branch=push_branch,
            remote=remote,
            files=[change.path for change in changes],
            report=report,
        )
        raise typer.Exit()

    commit_hashes = apply_execution_plan(repo, execution_plan, intent.push, remote, push_branch)
    console.print(f"[green]Created {len(commit_hashes)} commit(s).[/green]")
    if intent.push:
        console.print(f"[green]Pushed to {remote}/{push_branch}[/green]")
    _write_run_event(
        cfg=cfg,
        event="override_used" if override_used else "executed",
        blocked=report.blocked,
        execute=True,
        override=override_used,
        reason=reason,
        branch=push_branch,
        remote=remote,
        files=[change.path for change in changes],
        report=report,
        commit_hashes=commit_hashes,
    )