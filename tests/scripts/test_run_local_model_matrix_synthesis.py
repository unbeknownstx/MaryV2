from pathlib import Path
import pytest

from scripts.run_local_model_matrix import server_command, validate_pair


def test_local_matrix_server_command_loads_adapter_disabled_for_request_local_scaling():
    command = server_command("llama-server", model_path=Path("base.gguf"), adapter_path=Path("style.gguf"), port=18080)
    assert command[:3] == ["llama-server", "-m", "base.gguf"]
    assert "--lora" in command
    assert "--lora-init-without-apply" in command
    assert "shell" not in " ".join(command)


def test_local_matrix_rejects_wrong_adapter_base():
    with pytest.raises(ValueError):
        validate_pair(
            {"id": "base", "repository": "a/base", "upstream_base": "a/base"},
            {"id": "adapter", "required_base": "b/base"},
        )
