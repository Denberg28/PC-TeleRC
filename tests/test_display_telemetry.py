from types import SimpleNamespace

from pctelerc.mavlink import MavlinkService, MavlinkSnapshot
from pctelerc.core import LinkState


def message(kind,sys=1,**fields):
    return SimpleNamespace(get_type=lambda:kind,get_srcSystem=lambda:sys,get_srcComponent=lambda:1,**fields)


def test_gps_requires_locked_vehicle_and_does_not_refresh_heartbeat():
    service=MavlinkService()
    gps=message('GPS_RAW_INT',fix_type=3,lat=136200000,lon=1231900000,satellites_visible=12,vel=123,cog=9000)
    service._handle_message(gps,100)
    assert service.snapshot().latitude is None
    service._snapshot=MavlinkSnapshot(state=LinkState.CONNECTED,vehicle_system=1,vehicle_component=1,last_heartbeat=90)
    service._handle_message(message('GPS_RAW_INT',sys=2,**{k:v for k,v in vars(gps).items() if not k.startswith('get_')}),100)
    assert service.snapshot().latitude is None
    service._handle_message(gps,100)
    snap=service.snapshot()
    assert (snap.latitude,snap.longitude,snap.speed,snap.heading,snap.satellites) == (13.62,123.19,1.23,90,12)
    assert snap.last_heartbeat == 90 and not snap.control_enabled


def test_bad_fix_and_out_of_range_positions_not_used():
    service=MavlinkService()
    service._snapshot=MavlinkSnapshot(vehicle_system=1,vehicle_component=1)
    for fix,lat in [(2,136200000),(3,910000000)]:
        service._handle_message(message('GPS_RAW_INT',fix_type=fix,lat=lat,lon=1231900000),100)
        assert service.snapshot().latitude is None


def test_global_position_and_battery_are_read_only_and_unknown_values_stay_unknown():
    service=MavlinkService()
    service._snapshot=MavlinkSnapshot(vehicle_system=1,vehicle_component=1,gps_fix=3,last_heartbeat=80)
    service._handle_message(message('GLOBAL_POSITION_INT',lat=136200000,lon=1231900000,vx=300,vy=400,hdg=65535),100)
    assert service.snapshot().speed == 5 and service.snapshot().heading is None
    service._handle_message(message('SYS_STATUS',voltage_battery=12400,battery_remaining=75),101)
    assert service.snapshot().voltage == 12.4 and service.snapshot().battery_remaining == 75
    service._handle_message(message('SYS_STATUS',voltage_battery=65535,battery_remaining=-1),102)
    assert service.snapshot().voltage is None and service.snapshot().battery_remaining is None
    assert service.snapshot().last_heartbeat == 80
