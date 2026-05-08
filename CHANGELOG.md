# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog and versioning follows SemVer conventions.

## [0.2.0] - 2026-05-08

### Added
- Intent-first Git commands: `safepush status`, `safepush preview`, `safepush push`, and `safepush fix`.
- Safe remediation mode: `safepush fix --apply` and non-interactive `--yes`.
- Remote remediation support: `safepush fix --apply --remote-url <url>` for `NO_REMOTE`.
- Smart commit planning mode (`git.commit_mode = "smart"`) with grouped commits by category and area.
- Deterministic, diff-aware commit message generation with conventional types and readable scopes.
- Optional message provider scaffold (`commit.message_mode = deterministic|llm|hybrid`) with deterministic fallback.
- New test coverage for gitops deletion handling and commit message generation quality.

### Changed
- Commit subjects now prioritize human-readable intent over generic file-count summaries.
- `preview` command introduced as the clear dry-run intent alias.

### Fixed
- Execution no longer crashes when a commit group includes deleted tracked files.
- Config parsing now surfaces invalid TOML as controlled user-facing errors.

## [0.1.0] - 2026-05-07

### Added
- Initial CLI foundations: `doctor`, `scan`, `plan`, `run`, and interactive mode.
- Safety scanner with denylist, secret pattern, and PII checks.
- Audit logging for scan and run outcomes.
- Basic grouped/per-file deterministic commit planning.
