"""Windows UDP construction must bind ephemeral locally, then address the rover."""

from types import SimpleNamespace

import pytest

from pctelerc.mission_protocol import client


def test_windows_udpout_restores_remote_after_ephemeral_bind(monkeypatch):
    calls = []
    link = SimpleNamespace(destination_addr=("127.0.0.1", 0), address="127.0.0.1:0")

    def connect(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return link

    monkeypatch.setattr(client, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(client.mavutil, "mavlink_connection", connect)
    assert client.open_endpoint("udpout:127.0.0.1:14550") is link
    assert calls == [("udpout:127.0.0.1:0", dict(
        source_system=255, source_component=190, dialect="common"))]
    assert link.destination_addr == ("127.0.0.1", 14550)
    assert link.address == "127.0.0.1:14550"


def test_other_platform_preserves_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(client, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(client.mavutil, "mavlink_connection",
                        lambda endpoint, **kwargs: calls.append(endpoint) or object())
    client.open_endpoint("udpout:127.0.0.1:14550")
    assert calls == ["udpout:127.0.0.1:14550"]


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_windows_rejects_invalid_remote_port(monkeypatch, port):
    monkeypatch.setattr(client, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(client.mavutil, "mavlink_connection",
                        lambda *args, **kwargs: pytest.fail("Invalid destination opened"))
    with pytest.raises(ValueError, match="1..65535"):
        client.open_endpoint(f"udpout:127.0.0.1:{port}")
