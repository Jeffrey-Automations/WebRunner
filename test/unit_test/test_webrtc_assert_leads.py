"""webrtc_assert: assert_sdp_has_codec rejects a side it does not know."""
import pytest

from je_web_runner.utils.webrtc_assert.peer import (
    ConnectionState, IceState, PeerSnapshot, WebRtcAssertError, assert_sdp_has_codec,
)


def _snapshot() -> PeerSnapshot:
    return PeerSnapshot(
        connection_state=ConnectionState.CONNECTED, ice_connection_state=IceState.CONNECTED,
        local_sdp="a=rtpmap:96 VP8/90000", remote_sdp="a=rtpmap:111 opus/48000/2",
    )


def test_unknown_side_is_refused_instead_of_read_as_remote():
    with pytest.raises(WebRtcAssertError, match="side must be"):
        assert_sdp_has_codec(_snapshot(), "opus", side="Local")


def test_both_sides_still_work():
    assert_sdp_has_codec(_snapshot(), "VP8", side="local")
    assert_sdp_has_codec(_snapshot(), "opus", side="remote")
    with pytest.raises(WebRtcAssertError, match="does not advertise"):
        assert_sdp_has_codec(_snapshot(), "opus", side="local")
