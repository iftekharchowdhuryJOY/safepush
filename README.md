# safepush

[![Tests](https://img.shields.io/badge/tests-19%20passing-brightgreen)](https://github.com/<your-org-or-user>/safepush/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange)](https://github.com/<your-org-or-user>/safepush)

`safepush` is a safety-first git automation CLI. It scans changed files for risky content, builds deterministic commit plans, and can execute commit/push with strict guardrails. You don't need to worry about anymore commit messages. safepush will write messages for you to understand your code and changes.

Current version: `0.2.0`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Initialize config:

```bash
safepush config init
```

## Core Commands

- `safepush doctor`: validate repo/config/remote readiness.
- `safepush status`: plain-English git state and blockers.
- `safepush scan`: scan changed/untracked files and print safety findings.
- `safepush plan`: show deterministic commit grouping and messages.
- `safepush run`: run the full pipeline (scan -> plan -> dry-run or execute).
- `safepush preview`: intent command for dry-run preview (no git writes).
- `safepush push`: intent command for safe stage/commit/push (or `--dry-run` preview).
- `safepush fix`: diagnose common git blockers and show remediation actions.
- `safepush fix --apply`: apply safe auto-remediations (with confirmation, or `--yes`).
- `safepush fix --apply --remote-url <url>`: auto-remediate missing remote configuration.
- `safepush` (no subcommand): launch interactive wizard flow.

## Workflows

### Safe preview (default)

```bash
safepush run
```

By default (`dry_run_default=true`), this prints what would be committed/pushed without modifying git state.

### Execute commit + push

```bash
safepush run --execute
```

This creates commits using configured commit mode and pushes to configured remote/branch target.

### Override a blocked policy finding (one run only)

```bash
safepush run --execute --override --reason "test fixture contains fake key"
```

Overrides are never persistent and require explicit reason text each run.

## Safety Model

`safepush` blocks by default for high-risk findings:

- denylist file path matches (`denylist_path`)
- secret regex matches (`secret_pattern`)
- PII regex matches (`pii_pattern`)

Fail-closed behavior:

- scanner/runtime failures (`scanner_error`) are hard stops
- unknown/degraded safety state is non-overridable
- missing critical prerequisites (for strict execution) blocks execution

Override policy:

- overridable: `denylist_path`, `secret_pattern`, `pii_pattern`
- non-overridable: `scanner_error` and degraded-confidence safety states
- requires both `--override` and `--reason`

## Commit and Push Behavior

Commit grouping is controlled by config:

- `git.commit_mode = "grouped"`: one commit for all planned files
- `git.commit_mode = "per_file"`: one commit per file
- `git.commit_mode = "smart"`: split commits by file category/top-level area

Push target:

- remote from `git.remote` (default `origin`)
- branch from `git.branch` if set, otherwise current branch

Commit message mode is configurable:

- `commit.message_mode = "deterministic"`: built-in diff-aware message generation (default)
- `commit.message_mode = "llm"` or `"hybrid"`: reserved for optional model-assisted generation with deterministic fallback

## Interactive Wizard

Running `safepush` without a subcommand starts wizard mode:

1. Preflight checks (repo, branch, remote, config)
2. Scan summary and block outcome
3. Optional override flow (with reason + confirmation)
4. Plan preview (grouped/per-file commits)
5. Execute confirmation (respects dry-run default)
6. Audit event logging

## Audit Logs

Audit log path is configurable (`audit_log_path`, default `.safepush-audit.log`).

Events include:

- blocked
- aborted
- dry_run
- executed
- override_used

Run events record timestamp, branch, remote, files, findings summary, override reason, and created commit hashes.

## Testing

```bash
pytest -q
```

## Release Discipline

For every major feature or important bug fix:

1. Update user-facing behavior docs in `README.md`.
2. Add an entry to `CHANGELOG.md`.
3. Bump version in `pyproject.toml`.
4. Run tests before pushing:

```bash
python -m pytest -q
```

Version bump guide:

- patch (`x.y.Z`): bug fixes only
- minor (`x.Y.0`): backward-compatible features
- major (`X.0.0`): breaking CLI or behavior contracts

## GitHub Beta Launch (1-Week Dogfooding)

If you are not publishing to PyPI yet, this project is still easy to share and validate from GitHub.

### Install from GitHub

Using pipx (recommended for CLI tools):

```bash
pipx install "git+https://github.com/<your-org-or-user>/safepush.git"
```

Using pip:

```bash
pip install "git+https://github.com/<your-org-or-user>/safepush.git"
```

### Command Matrix

- `safepush doctor`: validate repo/config/remote readiness (no git writes).
- `safepush scan`: show safety findings on changed files (no git writes).
- `safepush plan`: show deterministic commit plan (no git writes).
- `safepush run`: full flow in dry-run mode by default (no git writes).
- `safepush run --execute`: execute commit/push flow (writes git state).
- `safepush`: interactive wizard flow (writes only after explicit confirmation).

### Override Semantics (Explicit and One-Run Only)

- Override is never persisted in config.
- `--override` requires a non-empty `--reason`.
- Overridable findings: `denylist_path`, `secret_pattern`, `pii_pattern`.
- Non-overridable hard stops include scanner/runtime failures (`scanner_error`).

Example:

```bash
safepush run --execute --override --reason "test fixture contains fake key"
```

### Audit Log Example

Default audit log file: `.safepush-audit.log`

Example run-event line:

```text
[2026-05-08T03:20:00+00:00] event=override_used blocked=True mode=execute override=True branch=main remote=origin files=src/app.py findings=secret_pattern:1 reason='test fixture contains fake key' commits=abc123
```

### Dogfooding Focus (Week 1)

- false positives and false negatives in detection
- override frequency and reason quality
- clarity of CLI prompts/messages
- git edge cases (detached HEAD, missing remote, no-change state)

## Known Limitations (Beta)

- Detection rules are regex-based and may produce false positives or miss edge-case secrets.
- `pathspec` fallback uses basic glob matching when dependency is unavailable.
- Interactive flow is terminal-driven and not yet optimized for non-interactive CI sessions.
- Preflight safety checks prioritize fail-closed behavior; some borderline states may block until rules are tuned.

## Getting Help

- Open a GitHub issue using:
  - `Dogfooding bug report (week 1)` for real workflow trial issues.
  - `Bug report` for general defects.
  - `Feature request` for enhancements.
- Include command used, expected behavior, actual output, and relevant `.safepush-audit.log` lines.
- For quick start support, run `safepush doctor` and attach its output in your issue.