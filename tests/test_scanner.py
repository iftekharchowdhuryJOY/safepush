from pathlib import Path

from safepush.config import AppConfig
from safepush.models import FileChange
from safepush.scanner import scan_changes


def test_denylist_blocks(tmp_path: Path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("HELLO=world", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    report = scan_changes([FileChange(path=".env", status="??")], AppConfig())
    assert report.blocked is True
    assert any(x.kind == "denylist_path" for x in report.findings)


def test_secret_pattern_blocks(tmp_path: Path, monkeypatch):
    f = tmp_path / "app.py"
    f.write_text('api_key = "abcd1234abcd1234"', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    report = scan_changes([FileChange(path="app.py", status="M")], AppConfig())
    assert report.blocked is True
    assert any(x.kind == "secret_pattern" for x in report.findings)
