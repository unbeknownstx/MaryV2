from pathlib import Path

from mary.tools.filesystem import FilesystemClient, FilesystemConfig
from mary.tools.repository_map import RepositoryMapClient, register_repository_map_tool
from mary.tools.registry import PermissionLevel, ToolRegistry


def _filesystem(root: Path) -> FilesystemClient:
    return FilesystemClient(FilesystemConfig(workspace_roots=[root]))


def test_repository_map_extracts_python_symbols_and_ranks_query(tmp_path: Path):
    (tmp_path / "mary").mkdir()
    (tmp_path / "mary" / "worker.py").write_text(
        "class SpecialistWorker:\n    pass\n\ndef run_worker():\n    return True\n",
        encoding="utf-8",
    )
    (tmp_path / "mary" / "other.py").write_text("def unrelated():\n    pass\n", encoding="utf-8")

    client = RepositoryMapClient(_filesystem(tmp_path))
    result = client.build("SpecialistWorker", limit=10)

    assert result["execution"] is False
    assert result["mutation"] is False
    assert result["files"][0]["path"] == "mary/worker.py"
    assert "SpecialistWorker" in result["files"][0]["symbols"]
    assert "run_worker" in result["files"][0]["symbols"]


def test_repository_map_skips_vendor_cache_and_symlink(tmp_path: Path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "bad.ts").write_text("export function Bad() {}", encoding="utf-8")
    (tmp_path / "app.py").write_text("def good():\n    pass\n", encoding="utf-8")

    target = tmp_path / "outside.py"
    target.write_text("def outside():\n    pass\n", encoding="utf-8")
    link = tmp_path / "linked.py"
    try:
        link.symlink_to(target)
    except OSError:
        pass

    result = RepositoryMapClient(_filesystem(tmp_path)).build(limit=20)
    paths = {item["path"] for item in result["files"]}
    assert "app.py" in paths
    assert "node_modules/bad.ts" not in paths
    assert "linked.py" not in paths


def test_large_files_are_not_read_into_repository_map(tmp_path: Path):
    (tmp_path / "small.py").write_text("def small():\n    pass\n", encoding="utf-8")
    (tmp_path / "huge.py").write_text("x = 1\n" * 10000, encoding="utf-8")
    client = RepositoryMapClient(_filesystem(tmp_path), max_file_bytes=8192)
    result = client.build(limit=20)
    paths = {item["path"] for item in result["files"]}
    assert "small.py" in paths
    assert "huge.py" not in paths
    assert result["skipped_large"] >= 1


def test_repository_map_tool_is_safe_read_only(tmp_path: Path):
    registry = ToolRegistry()
    client = register_repository_map_tool(registry, filesystem=_filesystem(tmp_path))
    definition = registry.get("code_repository_map")
    assert definition is not None
    assert definition.permission_level == PermissionLevel.SAFE
    assert definition.external_access is False
    assert definition.mutates_state is False
    assert client is not None
