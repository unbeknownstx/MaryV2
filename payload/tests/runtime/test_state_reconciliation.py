from pathlib import Path

from mary.runtime.state_reconciliation import StateReconciler


def test_reconciliation_classifies_identical_conflict_and_unique(tmp_path: Path):
    local = tmp_path / "local"
    cloud = tmp_path / "cloud"
    local.mkdir(); cloud.mkdir()
    (local / "memory").mkdir(); (cloud / "memory").mkdir()
    (local / "memory" / "same.json").write_text('{"a":1}', encoding="utf-8")
    (cloud / "memory" / "same.json").write_text('{"a":1}', encoding="utf-8")
    (local / "memory" / "conflict.json").write_text('{"v":"local"}', encoding="utf-8")
    (cloud / "memory" / "conflict.json").write_text('{"v":"cloud"}', encoding="utf-8")
    (local / "memory" / "only.json").write_text('{"local":true}', encoding="utf-8")

    plan = StateReconciler.plan({"local": local, "cloud": cloud})
    classes = {item["relative_path"]: item["classification"] for item in plan["items"]}
    assert classes["memory/same.json"] == "identical"
    assert classes["memory/conflict.json"] == "conflict"
    assert classes["memory/only.json"] == "unique_candidate"


def test_reconciliation_ignores_secrets(tmp_path: Path):
    root = tmp_path / "state"
    root.mkdir()
    (root / ".env").write_text("SECRET=x", encoding="utf-8")
    (root / "memory.json").write_text("{}", encoding="utf-8")
    inventory = StateReconciler.inventory({"state": root})["state"]
    assert [item.relative_path for item in inventory] == ["memory.json"]
