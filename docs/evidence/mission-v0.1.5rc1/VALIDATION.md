# v0.1.5rc1 host validation

- Python 3.12; PySide6 6.11.2; pymavlink 2.4.50; pygame-ce 2.5.8; pyserial 3.5.
- Full application regression: 235 passed. Includes 20 mission planning/session/
  protocol-peer tests, actual native USB envelope and MAVLink2 upload/readback/
  START/HOLD simulation, retries, NACK/ACK-loss, foreign rover filtering, GUI lease,
  cancelled confirmation, Escape cleanup and manual-session exclusion.
- Compileall: PASS. Publish-script tests: 13 passed. UI/media check: 24 checks PASS
  (camera decode, offline tiles, logo, cockpit, authority locks, mission codec/cleanup).
- Protocol input archive SHA256:
  204127c329b85bfd92011686294fb264b90546b5294718fd9a19e514fedf6fdb.
- Existing firmware, motor converter, manual transport/control worker unchanged.
- Protocol peer tests are not ArduRover SITL, RF, physical FC or hardware validation.
- Windows packaging/frozen validation is recorded by the dedicated workflow;
  local Linux results do not establish those Windows results.
- Physical RC takeover, radio interruption, FC loss timing/stopping distance,
  independent auxiliary cutoff and multi-rover selection require bench acceptance.
