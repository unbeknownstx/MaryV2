from __future__ import annotations

from scripts import doctor


def test_doctor_loads_local_env_without_printing_secret_value(tmp_path, monkeypatch, capsys):
    fixture_value = "doctor-test-value"
    (tmp_path / ".env").write_text(f"GROQ_API_KEY={fixture_value}\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("GROQ_API_KEY=your_groq_key_here\n", encoding="utf-8")
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package-lock.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    assert doctor.main() == 0
    output = capsys.readouterr().out
    assert "GROQ_API_KEY: configured" in output
    assert fixture_value not in output
