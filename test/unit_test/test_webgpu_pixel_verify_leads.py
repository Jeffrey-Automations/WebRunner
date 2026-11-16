"""webgpu_pixel_verify: malformed input raises the library's own error."""
import base64

import pytest

from je_web_runner.utils.webgpu_pixel_verify.pixel import (
    CanvasFrame, WebgpuPixelVerifyError, assert_mean_in_band, parse_frame,
)


@pytest.mark.parametrize("payload", [
    {"width": None, "height": 2, "rgba_b64": ""},
    {"width": 2, "height": [1], "rgba_b64": ""},
])
def test_parse_frame_with_a_size_that_is_not_a_number(payload):
    with pytest.raises(WebgpuPixelVerifyError, match="width or height"):
        parse_frame(payload)


def test_parse_frame_still_reads_a_good_frame():
    frame = parse_frame({"width": 1, "height": 1, "rgba_b64": base64.b64encode(bytes([1, 2, 3, 4])).decode()})
    assert frame.rgba == bytes([1, 2, 3, 4])


@pytest.mark.parametrize("channel", [None, 0, "rg", ""])
def test_channel_must_be_one_of_the_four_letters(channel):
    frame = CanvasFrame(width=1, height=1, rgba=bytes([10, 20, 30, 255]))
    with pytest.raises(WebgpuPixelVerifyError, match="channel"):
        assert_mean_in_band(frame, channel=channel, min_value=0, max_value=255)
