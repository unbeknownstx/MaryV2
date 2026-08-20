from __future__ import annotations

from scripts import verify_release_hygiene as hygiene


def test_local_env_is_allowed_when_gitignored(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text(".env\ndata/\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=do-not-read-this-file\n", encoding="utf-8")
    (tmp_path / "safe.py").write_text("VALUE = 'safe'\n", encoding="utf-8")
    monkeypatch.setattr(hygiene, "ROOT", tmp_path)

    assert hygiene.main() == 0


def test_local_env_fails_hygiene_when_not_gitignored(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text("data/\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=do-not-read-this-file\n", encoding="utf-8")
    monkeypatch.setattr(hygiene, "ROOT", tmp_path)

    assert hygiene.main() == 1


def test_releasable_source_still_fails_on_embedded_raw_secret(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text(
        'API_KEY="sk-' + ('a' * 40) + '"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(hygiene, "ROOT", tmp_path)

    assert hygiene.main() == 1
