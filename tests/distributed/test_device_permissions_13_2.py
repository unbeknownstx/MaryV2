import json

import pytest

from mary.distributed import DeviceExecutionPermissions


def test_device_permissions_default_deny_and_persist_explicit_allow(tmp_path):
    path = tmp_path / "permissions.json"
    permissions = DeviceExecutionPermissions(path)
    assert permissions.allowed() == set()
    assert permissions.is_allowed("personal_search") is False

    permissions.allow("personal_search")
    assert permissions.is_allowed("personal_search") is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["allowed_capabilities"] == ["personal_search"]

    permissions.deny("personal_search")
    assert permissions.allowed() == set()


def test_device_permissions_refuse_unimplemented_execution_types(tmp_path):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    with pytest.raises(ValueError):
        permissions.allow("shell")
