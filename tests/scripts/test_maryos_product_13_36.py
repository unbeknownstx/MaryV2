from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_maryos_foundation_reuses_home_node_and_has_no_runtime_shell():
    host = _text("mary/distributed/os_environment.py")
    status = _text("scripts/maryos_status.py")
    node = _text("scripts/run_home_node.py")
    assert "MaryOSEnvironmentProfile" in node
    assert "subprocess" not in host
    assert "os.system" not in host
    assert "Popen(" not in host
    assert "subprocess" not in status
    assert "arbitrary_shell" in status


def test_maryos_systemd_service_is_user_level_and_hardened():
    unit = _text("maryos/systemd/mary-home-node.service.template")
    assert "scripts.run_home_node" in unit
    assert "NoNewPrivileges=true" in unit
    assert "EnvironmentFile=-%h/.config/maryv2/node.env" in unit
    assert "User=root" not in unit
    assert "sudo" not in unit


def test_maryos_installer_never_escalates_privileges_or_autostarts_by_default():
    installer = _text("maryos/install-user-service.sh")
    assert "sudo " not in installer
    assert 'if [ "${1:-}" = "--enable" ]' in installer
    assert "systemctl --user" in installer


def test_maryos_contract_keeps_omarchy_optional_and_core_canonical():
    architecture = _text("docs/architecture/MARYOS_LINUX_SUBSTRATE_13_36.md")
    root = _text("MARY_ROOT.md")
    assert "Omarchy is not a Core" in architecture
    assert "no OS mutation executor" in architecture
    assert "Operating environment rule" in root
    assert "never becomes a second Mary" in root
