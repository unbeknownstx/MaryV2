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


def test_dependency_environments_are_excluded_from_secret_scan(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text(".env\n.venv*/\n.pythonlibs/\n", encoding="utf-8")
    for directory in (".venv-1", ".venv_test", "venv-old", ".pythonlibs"):
        target = tmp_path / directory
        target.mkdir()
        (target / "third_party.py").write_text(
            'API_KEY="sk-' + ('x' * 40) + '"\n',
            encoding="utf-8",
        )
    monkeypatch.setattr(hygiene, "ROOT", tmp_path)

    assert hygiene.main() == 0


def test_safe_test_and_placeholder_assignments_do_not_trigger_hygiene(tmp_path, monkeypatch):
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "fixture.py").write_text(
        'API_KEY="test-key"\nTAVILY_API_KEY="tvly-test-key"\n',
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text(
        "OPENAI_API_KEY=your_openai_key_here\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hygiene, "ROOT", tmp_path)

    assert hygiene.main() == 0
