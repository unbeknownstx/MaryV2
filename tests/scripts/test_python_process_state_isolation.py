from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_probe(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source, str(ROOT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_direct_pytest_conftest_isolates_before_config_and_restores_exactly():
    probe = r'''
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

root = Path(sys.argv[1])
sentinels = {
    "MARY_DATA_DIR": "prior-data",
    "MARY_ENV_FILE": "prior-env",
    "MARY_RESERVOIR_STORAGE": "persistent",
    "PYTEST_DEBUG_TEMPROOT": "prior-pytest-temp",
    "PYTEST_ADDOPTS": "-q",
    "GROQ_API_KEY": "explicit-test-sentinel",
}
os.environ.update(sentinels)
assert "mary.core.config" not in sys.modules
spec = importlib.util.spec_from_file_location(
    "maryv2_isolation_probe_conftest",
    root / "tests" / "conftest.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

from mary.core.config import Config

session_root = module._SESSION_ROOT
assert session_root.parent == Path(tempfile.gettempdir()).resolve()
assert session_root.name.startswith("maryv2-pytest-session-")
assert Config().paths.data.resolve() == module._SESSION_DATA_ROOT.resolve()
assert Path(os.environ["MARY_ENV_FILE"]) == module._SESSION_ENV_FILE
assert not module._SESSION_ENV_FILE.exists()
assert os.environ["MARY_RESERVOIR_STORAGE"] == "memory"
assert os.environ["PYTEST_ADDOPTS"] == "-p no:cacheprovider"
assert "GROQ_API_KEY" not in os.environ

module._restore_test_environment()
assert not session_root.exists()
assert all(os.environ.get(name) == value for name, value in sentinels.items())
'''
    completed = _run_probe(probe)
    assert completed.returncode == 0, completed.stderr


def test_explicit_live_pytest_preserves_exported_credentials_but_not_dotenv_state():
    probe = r'''
import importlib.util
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
os.environ["MARY_RUN_LIVE_TESTS"] = "1"
os.environ["GROQ_API_KEY"] = "explicit-live-sentinel"
spec = importlib.util.spec_from_file_location(
    "maryv2_live_isolation_probe_conftest",
    root / "tests" / "conftest.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
assert os.environ["GROQ_API_KEY"] == "explicit-live-sentinel"
assert os.environ["MARY_RESERVOIR_STORAGE"] == "memory"
assert not Path(os.environ["MARY_ENV_FILE"]).exists()
session_root = module._SESSION_ROOT
module._restore_test_environment()
assert not session_root.exists()
assert os.environ["GROQ_API_KEY"] == "explicit-live-sentinel"
'''
    completed = _run_probe(probe)
    assert completed.returncode == 0, completed.stderr


def test_release_runner_and_standalone_verifier_import_before_no_mary_config():
    probe = r'''
import importlib
import os
from pathlib import Path
import sys
import tempfile

root = Path(sys.argv[1])
os.environ["MARY_DATA_DIR"] = "prior-data"
os.environ["MARY_ENV_FILE"] = "prior-env"
release = importlib.import_module("scripts.run_release_verification")
verifier = importlib.import_module("scripts.verify_production_hybrid_dialogue_12_12_3")
assert "mary.core.config" not in sys.modules

with release._offline_process_environment() as isolation:
    from mary.core.config import Config
    assert isolation["root"].parent == Path(tempfile.gettempdir()).resolve()
    assert Config().paths.data.resolve() == isolation["data"].resolve()
    assert not isolation["env_file"].exists()
release_root = isolation["root"]
assert not release_root.exists()
assert os.environ["MARY_DATA_DIR"] == "prior-data"
assert os.environ["MARY_ENV_FILE"] == "prior-env"

with verifier.isolated_verifier_environment() as isolation:
    assert isolation["root"].parent == Path(tempfile.gettempdir()).resolve()
    assert Config().paths.data.resolve() == isolation["data"].resolve()
    assert not isolation["env_file"].exists()
verifier_root = isolation["root"]
assert not verifier_root.exists()
assert os.environ["MARY_DATA_DIR"] == "prior-data"
assert os.environ["MARY_ENV_FILE"] == "prior-env"
'''
    completed = _run_probe(probe)
    assert completed.returncode == 0, completed.stderr
