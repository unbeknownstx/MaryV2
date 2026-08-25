from mary.protocol.client import MaryClient


def test_client_preserves_device_identity():
    client = MaryClient("https://example.invalid", token="secret", device_id="macbook")
    assert client.device_id == "macbook"
    assert client.base_url == "https://example.invalid"
