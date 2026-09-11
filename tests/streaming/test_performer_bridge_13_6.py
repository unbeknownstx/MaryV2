import pytest

from mary.streaming import PerformerBridge, PerformerConfig, StreamPermissionError


def config(**overrides):
    values = dict(
        twitch_enabled=True,
        twitch_mode="listen",
        approved_channels=("mary",),
        twitch_write_chat=False,
        twitch_credentials_configured=True,
        obs_enabled=True,
        obs_host="127.0.0.1",
        obs_port=4455,
        obs_allow_scene_switch=True,
        obs_password_configured=True,
    )
    values.update(overrides)
    return PerformerConfig(**values)


def test_twitch_input_is_untrusted_and_channel_bounded():
    bridge = PerformerBridge(config())
    event = bridge.ingest_chat(channel="#mary", author="viewer", text="hello")
    assert event.metadata["authority"] == "untrusted_audience"
    assert event.metadata["channel"] == "mary"
    with pytest.raises(StreamPermissionError):
        bridge.ingest_chat(channel="other", author="viewer", text="hello")


def test_outbound_chat_requires_existing_policy_and_explicit_permission():
    with pytest.raises(StreamPermissionError):
        PerformerBridge(config()).authorize_chat_send(channel="mary")
    with pytest.raises(StreamPermissionError):
        PerformerBridge(config(twitch_mode="cohost", twitch_write_chat=True)).authorize_chat_send(channel="mary")
    allowed = PerformerBridge(
        config(twitch_mode="cohost", twitch_write_chat=True),
        allowed_actions={"twitch.send_chat"},
    )
    assert allowed.authorize_chat_send(channel="mary")["action"] == "send_chat"


def test_obs_has_finite_allowlist_policy_and_write_permissions():
    bridge = PerformerBridge(config())
    assert bridge.authorize_obs("get_stream_status")["action"] == "get_stream_status"
    with pytest.raises(StreamPermissionError):
        bridge.authorize_obs("set_current_scene", scene="Mary")
    with pytest.raises(StreamPermissionError):
        PerformerBridge(
            config(obs_allow_scene_switch=False), allowed_actions={"obs.set_current_scene"}
        ).authorize_obs("set_current_scene", scene="Mary")
    allowed = PerformerBridge(config(), allowed_actions={"obs.set_current_scene"})
    assert allowed.authorize_obs("set_current_scene", scene="Mary")["arguments"]["scene"] == "Mary"
    with pytest.raises(ValueError):
        bridge.authorize_obs("CallVendorRequest", request="anything")


def test_from_env_delegates_to_existing_twitch_obs_policy(monkeypatch):
    monkeypatch.setenv("MARY_SKILL_TWITCH", "true")
    monkeypatch.setenv("MARY_TWITCH_MODE", "cohost")
    monkeypatch.setenv("MARY_TWITCH_APPROVED_CHANNELS", "mary")
    monkeypatch.setenv("MARY_SKILL_OBS", "true")
    monkeypatch.setenv("MARY_OBS_ALLOW_SCENE_SWITCH", "true")
    cfg = PerformerConfig.from_env()
    assert cfg.twitch_enabled is True
    assert cfg.twitch_write_chat is True
    assert cfg.obs_enabled is True
    assert cfg.obs_allow_scene_switch is True


def test_status_never_contains_secret_values(monkeypatch):
    monkeypatch.setenv("MARY_TWITCH_OAUTH_TOKEN", "super-secret-twitch")
    monkeypatch.setenv("MARY_OBS_PASSWORD", "super-secret-obs")
    status = str(PerformerConfig.from_env().status())
    assert "super-secret-twitch" not in status
    assert "super-secret-obs" not in status
