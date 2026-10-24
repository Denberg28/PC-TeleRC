"""Version identification and cancellation at real framed BASE status boundaries."""
from collections import deque
import threading
import pytest
from pymavlink.dialects.v20 import common as mav
from pctelerc.firmware_profiles import mission_capabilities
from pctelerc.mission_service import MissionService
from pctelerc.mission_transport import MissionUSB
from pctelerc.mission_protocol.usb_gateway import Decoder, encode
from test_mission_session import NativePeer, pump


@pytest.mark.parametrize('suffix,family', [(b'', 'Mission'),
    (b';unified=0.3.0', 'Unified LoRa'), (b';unified=0.4.0', 'Scalable LoRa')])
def test_supported_caps_preserve_wire_api_and_identify_board(suffix, family):
    caps, profile = mission_capabilities(b'TM2;fw=0.2.0;relays=2;mask=0'+suffix)
    assert caps == dict(firmware='0.2.0', relays=2, mask=0)
    assert profile.family == family
    assert profile.dynamic_routes == (family == 'Scalable LoRa')


@pytest.mark.parametrize('data', [
    b'TM2;fw=0.2.0;relays=2;mask=0;unified=0.5.0',
    b'TM2;fw=0.2.0;relays=2;mask=0;mask=256',
    b'TM2;fw=0.2.0;relays=3;mask=0',
    b'TM2;fw=0.2.0;relays=2;mask=16',
    b'TM2;fw=0.2.0;relays=2;mask=0;unified=',
    b'TF2;fw=0.2.0;relays=2;mask=0',
    b'TM2;fw=0.2.0;mask=0', b'\xff'])
def test_unsupported_or_ambiguous_caps_fail_closed(data):
    with pytest.raises(RuntimeError, match='Incompatible'):
        mission_capabilities(data)


def make_link(peer):
    link = MissionUSB.__new__(MissionUSB)
    link.rover, link.port = peer.rover, peer
    link.gate = threading.RLock()
    link.check = lambda: None
    link.status = lambda _: None
    link.capabilities = link.profile = None
    link.decoder, link.messages = Decoder(), deque(maxlen=64)
    link.mav = mav.MAVLink(link, srcSystem=255, srcComponent=190)
    return link


def test_capability_change_after_handshake_aborts_instead_of_changing_live_mask():
    peer = NativePeer(20)
    link = make_link(peer)
    link.handshake()
    peer.active = False
    peer.incoming.extend(encode(20, 3, b'TM2;fw=0.2.0;relays=2;mask=0;unified=0.4.0'))
    with pytest.raises(RuntimeError, match='capabilities changed'):
        link.recv_match()
    assert not peer.commands


@pytest.mark.parametrize('notice', [b'Route lost; commands discarded; rediscovering',
    b'Route learned; qualifying; commands discarded', b'RF fault; retry pending; control released',
    b'Command queue full'])
def test_route_reset_closes_worker_clears_verification_and_never_replays_start(qt_application, notice):
    peer = NativePeer(20)
    link = make_link(peer)
    service = MissionService(lambda *_: link)
    service.connect('COM9', 20)
    try:
        pump(service, lambda: service._confirmed)
        service.verified_digest = 'previous verified mission'
        peer.incoming.extend(encode(20, 2, notice))
        pump(service, lambda: not service.running)
        assert not service.verified_digest and not service._confirmed
        assert not peer.active and not peer.commands
        count = peer.heartbeats
        qt_application.processEvents()
        assert peer.heartbeats == count
        with pytest.raises(RuntimeError):
            service.submit('start', [])
    finally:
        service.close()


def test_initial_discovery_is_allowed_but_cannot_authorize_actions(qt_application):
    service = MissionService()
    service._base_status('Discovering nodes; no control commands')
    service._base_status('Route learned; qualifying; commands discarded')
    assert not service._confirmed and not service.verified_digest
    assert service.phase.startswith('Finding rover')


def test_transient_missed_manual_info_reply_is_retried_without_driving(monkeypatch):
    import serial
    from pctelerc.lora import Parser
    from pctelerc.transport import VehicleLoRa
    from test_lora import LoRaSerial, ACTIVE
    class DelayedInfo(LoRaSerial):
        requests = 0
        def write(self, data):
            self.requests += 1
            if self.requests == 1:
                return len(data)
            return super().write(data)
    monkeypatch.setattr(serial, 'Serial', DelayedInfo)
    link = VehicleLoRa('COM9')
    try:
        assert link.require_active_base(threading.Event(), timeout=1.5).active
        assert link.port.requests == 2
        assert all(Parser().feed(p, 0) == [b'TELERC_LORA_GET_V1'] for p in link.port.tx)
    finally:
        link.close()


def test_loss_during_start_readback_cancels_start_and_stops_heartbeats(qt_application):
    from pctelerc.mission_plan import Plan, Point, parse_text
    from pctelerc.mission_protocol.client import fingerprint
    class LostOnReadback(NativePeer):
        def write(self, data):
            result = super().write(data)
            for _, kind, raw in Decoder().feed(data):
                if kind == 1 and mav.MAVLink(None).parse_char(raw).get_type() == 'MISSION_REQUEST_LIST':
                    self.incoming.extend(encode(self.rover, 2, b'Route lost; commands discarded; rediscovering'))
            return result
    peer = LostOnReadback(3)
    service = MissionService(lambda *_: make_link(peer))
    items = parse_text(Plan([Point(13.6, 123.2)]).wpl())
    service.connect('COM9', 3)
    try:
        pump(service, lambda: service._confirmed)
        service.verified_digest = fingerprint(items, 3)
        service.submit('start', items)
        pump(service, lambda: not service.running)
        assert not service.verified_digest and not peer.commands
        assert not peer.active and service.jobs.empty()
    finally:
        service.close()
