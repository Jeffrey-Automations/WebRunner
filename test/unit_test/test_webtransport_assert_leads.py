"""webtransport_assert: the serialised payload is hex and its key says so."""
import json

from je_web_runner.utils.webtransport_assert.streams import DATAGRAM, RECEIVED, WtFrame, to_json


def test_to_dict_names_the_hex_payload_payload_hex():
    plain = WtFrame(direction=RECEIVED, channel=DATAGRAM, payload=b"\x00\xff\x10").to_dict()
    assert plain["payload_hex"] == "00ff10"
    assert bytes.fromhex(plain["payload_hex"]) == b"\x00\xff\x10"
    assert "payload_b64" not in plain
    assert "payload" not in plain


def test_to_json_uses_the_same_key():
    loaded = json.loads(to_json([WtFrame(direction=RECEIVED, channel=DATAGRAM, payload=b"hi")]))
    assert loaded[0]["payload_hex"] == "6869"
