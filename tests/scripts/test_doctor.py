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



def test_doctor_reports_presentation_readiness_without_requiring_body_assets(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env.example").write_text("", encoding="utf-8")
    (tmp_path / "desktop").mkdir()
    (tmp_path / "desktop" / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "desktop" / "package.json").write_text('{"dependencies":{"@pixiv/three-vrm":"3.5.5"}}', encoding="utf-8")

    expression = tmp_path / "mary" / "expression"
    expression.mkdir(parents=True)
    for name in ("performance_packet.py", "surface_performance.py", "motion_library.py"):
        (expression / name).write_text("", encoding="utf-8")

    motions = tmp_path / "assets" / "motions"
    motions.mkdir(parents=True)
    (motions / "README.md").write_text("motion policy", encoding="utf-8")

    mobile = tmp_path / "mobile_web"
    mobile.mkdir()
    (mobile / "app.js").write_text("function applyMobilePerformance() {}", encoding="utf-8")

    ios = tmp_path / "ios" / "MaryV2iOS" / "Sources"
    ios.mkdir(parents=True)
    (ios / "MaryStageView.swift").write_text("presentationExpression", encoding="utf-8")

    monkeypatch.setattr(doctor, "ROOT", tmp_path)

    assert doctor.main() == 0
    output = capsys.readouterr().out
    assert "Presentation readiness" in output
    assert "PASS  Surface performance projection" in output
    assert "PASS  PWA performance consumer" in output
    assert "PASS  Native iPhone performance stage" in output
    assert "WARN  Desktop Mary VRM" in output
