import json

from mary.creative import CreativeServiceRegistry


def test_creative_service_catalog_quotes_without_storing_secrets(monkeypatch):
    monkeypatch.setenv(
        "MARY_CREATIVE_SERVICE_CATALOG",
        json.dumps([
            {
                "provider": "example_video",
                "capability": "video.render",
                "model": "anime-v1",
                "cost_per_unit_usd": 5.0,
                "unit": "job",
                "metadata": {"api_key": "must-not-survive", "quality": "high"},
            }
        ]),
    )
    registry = CreativeServiceRegistry.from_environment()
    quote = registry.quote_job({"kind": "video.render", "budget_ceiling_usd": 5.0})
    assert quote["available"] is True
    assert quote["estimated_cost_usd"] == 5.0
    assert quote["within_budget_hint"] is True
    assert "api_key" not in quote["selected"]["metadata"]
    assert registry.snapshot()["execution_authority"] is False
