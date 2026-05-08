from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from typing import Any

try:
    import tomli_w  # type: ignore[reportMissingImports]
except ModuleNotFoundError:  # pragma: no cover - exercised only when dep missing
    tomli_w = None


DEFAULT_CONFIG_PATH = Path(".safepush.toml")


@dataclass
class ScannerConfig:
    enabled: bool = True
    detect_secrets: bool = True
    detect_pii: bool = True
    fail_closed: bool = True


@dataclass
class GitConfig:
    remote: str = "origin"
    branch: str = ""
    commit_mode: str = "grouped"  # grouped | per_file
    push: bool = True


@dataclass
class SafetyConfig:
    dry_run_default: bool = True
    allow_override_flag: bool = True
    deny_globs: list[str] = field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
            "id_rsa",
            "id_dsa",
            "credentials*.json",
            "*secret*",
            "*token*",
        ]
    )
    allow_globs: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    git: GitConfig = field(default_factory=GitConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    audit_log_path: str = ".safepush-audit.log"


def _deep_get(dct: dict, key: str, default):
    return dct.get(key, default) if isinstance(dct, dict) else default


def _toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _fallback_toml_dumps(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for section, value in data.items():
        if isinstance(value, dict):
            lines.append(f"[{section}]")
            for key, item in value.items():
                lines.append(f"{key} = {_toml_literal(item)}")
            lines.append("")
        else:
            lines.append(f"{section} = {_toml_literal(value)}")
    if lines and lines[-1] != "":
        lines.append("")
    return "\n".join(lines)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"Invalid config file '{path}': {exc}") from exc
    scanner = raw.get("scanner", {})
    git = raw.get("git", {})
    safety = raw.get("safety", {})

    return AppConfig(
        scanner=ScannerConfig(
            enabled=_deep_get(scanner, "enabled", True),
            detect_secrets=_deep_get(scanner, "detect_secrets", True),
            detect_pii=_deep_get(scanner, "detect_pii", True),
            fail_closed=_deep_get(scanner, "fail_closed", True),
        ),
        git=GitConfig(
            remote=_deep_get(git, "remote", "origin"),
            branch=_deep_get(git, "branch", ""),
            commit_mode=_deep_get(git, "commit_mode", "grouped"),
            push=_deep_get(git, "push", True),
        ),
        safety=SafetyConfig(
            dry_run_default=_deep_get(safety, "dry_run_default", True),
            allow_override_flag=_deep_get(safety, "allow_override_flag", True),
            deny_globs=_deep_get(safety, "deny_globs", SafetyConfig().deny_globs),
            allow_globs=_deep_get(safety, "allow_globs", []),
        ),
        audit_log_path=raw.get("audit_log_path", ".safepush-audit.log"),
    )


def init_default_config(path: Path = DEFAULT_CONFIG_PATH, force: bool = False) -> Path:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")

    default = {
        "scanner": {
            "enabled": True,
            "detect_secrets": True,
            "detect_pii": True,
            "fail_closed": True,
        },
        "git": {
            "remote": "origin",
            "branch": "",
            "commit_mode": "grouped",
            "push": True,
        },
        "safety": {
            "dry_run_default": True,
            "allow_override_flag": True,
            "deny_globs": SafetyConfig().deny_globs,
            "allow_globs": [],
        },
        "audit_log_path": ".safepush-audit.log",
    }

    if tomli_w is not None:
        rendered = tomli_w.dumps(default)
    else:
        rendered = _fallback_toml_dumps(default)
    path.write_text(rendered, encoding="utf-8")
    return path
