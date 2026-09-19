from mary.mobile.server import (
    MAX_CREATOR_IMAGE_BYTES,
    MAX_CREATOR_IMAGE_REQUEST_BYTES,
    MAX_REQUEST_BYTES,
)


def test_creator_image_route_keeps_general_mobile_body_limit_small():
    assert MAX_REQUEST_BYTES == 256_000
    assert MAX_CREATOR_IMAGE_BYTES <= 1_500_000
    assert MAX_CREATOR_IMAGE_REQUEST_BYTES > MAX_REQUEST_BYTES
    assert MAX_CREATOR_IMAGE_REQUEST_BYTES < 3_000_000
