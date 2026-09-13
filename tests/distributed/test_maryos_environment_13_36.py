from mary.distributed.os_environment import MaryOSEnvironmentProfile


def test_maryos_environment_is_diagnostic_only():
    profile = MaryOSEnvironmentProfile.detect().to_dict()
    assert profile["authority"] == "diagnostic_projection_only"
    assert profile["execution_authority"] is False
    assert isinstance(profile["package_managers"], list)
    assert profile["platform"]


def test_maryos_candidate_requires_linux_systemd():
    profile = MaryOSEnvironmentProfile(
        platform="linux",
        distro_id="arch",
        distro_name="Arch Linux",
        distro_version="",
        init_system="systemd",
        systemd_available=True,
        desktop_session="Hyprland",
        display_protocol="wayland",
        hyprland_session=True,
        quickshell_available=True,
        package_managers=("pacman",),
        omarchy_detected=True,
    )
    assert profile.maryos_candidate is True
    assert profile.to_dict()["execution_authority"] is False
