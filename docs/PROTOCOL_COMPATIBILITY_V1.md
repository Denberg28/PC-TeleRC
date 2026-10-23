# v1.0 protocol and firmware compatibility

| Application/profile | Matching firmware | Contract and limits |
| --- | --- | --- |
| TeleRC 1.0.0 ArduRover Wi-Fi | v1 FieldProtocol-enabled TeleRCBridge | MAVLink1 outbound, CRC/target allowlist; CH1 steering/CH2 drive; real FC heartbeat and physical CH7 permission for field actions |
| Go 1.0.4 ArduRover Wi-Fi | Same v1 TeleRCBridge | Real ArduRover heartbeat; RC_CHANNELS CH7 (>1800 us) permission; normal ARM and bounded request/HOLD support |
| Go 1.0.4 four-motor | MiniRover 1.2.4-go-4wd source in firmware/go | Go ownership/capability bit11, nonzero boot identity, 500 ms local driving timeout; no receiver in this build |
| Go 1.0.4 TT car | TeleRC_Go_TT_Car source in firmware/go | Separate rear-drive/front-steering profile with bounded steering jog; receiver support only when wired/enabled/validated |
| Go 1.0.4 balancer | Paired SBRB candidate in bridge/TT_Balancer_ESP32S3 | Go ownership bits11/12, nonzero boot identity; link loss cancels travel while local upright balance continues; explicit disarm removes torque; no receiver advertised |
| PC 1.0.0rc1 Mission | Complete provisioned TM2 0.2.0 role set | USB frame plus addressed authenticated radio; actual ArduRover heartbeat; one active rover session; 1–20 distinct offline plans; zero to two fixed nodes |
| PC manual legacy transports | Their separately documented matching firmware | Retained compatibility only; these are not interchangeable with Mission TM2 or Go ownership firmware |

Android applications retain their separate package IDs and existing signing identity.
Version numbers are not wire protocol negotiation. Source profiles are independently
versioned, and the manifest records exact build source and flags. Always flash the
complete matching LoRa role set generated together; public examples have RF OFF.

The v1 Field bridge fixes an actual compatibility gap: the older minimal bridge
accepted RC override and normal ARM only, rejecting parameter reads, message
interval requests, F servo commands and Guided destinations. Do not pair the new
field workflow with that old bridge. The new whitelist is narrow: no PARAM_SET,
force-arm, arbitrary modes, arbitrary position speed or motor servo outputs.

For the declared FC takeover profile, map the physical switch to CH7 and verify
RC7_OPTION=46, RC input calibration, finite RC override timeout and RC/GCS/mode
failsafes against the actual ArduRover version. Low/mid CH7 blocks field authority.
High CH7 permits software but does not prove receiver health or acquire control.
A fresh heartbeat cannot resume driving: neutral input and deliberate enable are
still required. The physical mode switch must interrupt Guided/AUTO operation;
blocking RC overrides alone does not stop navigation. Local disarm is an explicit
safety exception, not an automatic response to a mission link interruption.

Every profile rejects stale/foreign/malformed input within its implemented
contract. Legacy Wi-Fi still lacks end-to-end command authentication and full
replay protection; CRC and endpoint locking are not authentication. There is no
production security or physical safety certification in this candidate.

Software compilation/testing must be recorded separately from installation,
radio, power, motor, mission and takeover qualification. All physical pairings
remain NOT TESTED/BLOCKED until their restrained-wheel procedures pass. No 20-rover
RF capacity, simultaneous monitoring, dynamic routing or stable readiness claim
is made by the offline planning ID range.
