# Contributing to safepush

Thanks for contributing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Development Workflow

1. Create a feature branch.
2. Make focused changes with tests.
3. Run the full test suite:

```bash
python -m pytest -q
```

4. Open a pull request with:
   - problem statement,
   - approach summary,
   - test evidence.

## Coding Guidelines

- Keep behavior fail-closed for safety gates.
- Avoid destructive git operations in automation paths.
- Prefer explicit error messages and controlled exit codes.
- Update docs when behavior changes.

## Reporting Issues

Use GitHub issue templates:
- `Dogfooding Bug Report` for week-1 real workflow bugs.
- `Bug Report` for general defects.
- `Feature Request` for improvements.
