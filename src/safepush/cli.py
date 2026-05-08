from __future__ import annotations

from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from safepush.audit import write_audit_log
from safepush.config import DEFAULT_CONFIG_PATH, init_default_config, load_config
from safepush.gitops import changed_and_untracked, get_repo, has_remote


app = typer.Typer(help="Safe git automation CLI")
config_app = typer.Typer(help="Config operations")
app.add_typer(config_app, name="config")
console = Console()


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    # interactive mode will be Phase 3
    if ctx.invoked_subcommand is None:
        console.print("[yellow]Interactive mode arrives in Phase 3. Use `safepush --help` for now.[/yellow]")


@app.command()
def doctor():
    """Validate git/auth/config readiness."""
    cfg = load_config()
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
def scan(audit_log: bool = typer.Option(True, "--audit-log/--no-audit-log")):
    """Show risky files/secrets."""
    cfg = load_config()
    repo = get_repo()
    changes = changed_and_untracked(repo)

    if not changes:
        console.print("[green]No changed or untracked files.[/green]")
        raise typer.Exit()

    from safepush.scanner import scan_changes

    report = scan_changes(changes, cfg)

    table = Table(title="Scan report")
    table.add_column("Severity")
    table.add_column("Kind")
    table.add_column("Path")
    table.add_column("Detail")
    for f in report.findings:
        table.add_row(f.severity, f.kind, f.path, f"{f.detail}" + (f" (line {f.line_no})" if f.line_no else ""))

    if report.findings:
        console.print(table)
    else:
        console.print("[green]No findings.[/green]")

    console.print(f"Scanned files: {report.scanned_files}")
    console.print(f"Blocked: {'YES' if report.blocked else 'NO'}")

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
