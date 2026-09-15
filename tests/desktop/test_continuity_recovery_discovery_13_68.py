from __future__ import annotations

import json

from mary.desktop.continuity_recovery import inspect_continuity_root


def test_local_continuity_discovery_reports_counts_without_content(tmp_path):
    root = tmp_path / "data"
    (root / "memory").mkdir(parents=True)
    (root / "relationship").mkdir(parents=True)
    (root / "memory" / "memory.json").write_text(
        json.dumps({
            "episodic": [{"content": "private creator memory"}],
            "semantic": [{"value": "private semantic fact"}],
        }),
        encoding="utf-8",
    )
    (root / "relationship" / "relationship.json").write_text(
        json.dumps({
            "history": {"events": [{"description": "private history"}]},
            "milestones": {"milestones": [{"description": "private milestone"}]},
        }),
        encoding="utf-8",
    )

    result = inspect_continuity_root(root)

    assert result["recoverable_candidate"] is True
    assert result["counts"]["episodic"] == 1
    assert result["counts"]["semantic"] == 1
    assert result["counts"]["relationship_history"] == 1
    assert result["counts"]["relationship_milestones"] == 1
    rendered = json.dumps(result)
    assert "private creator memory" not in rendered
    assert "private semantic fact" not in rendered
    assert "private history" not in rendered
