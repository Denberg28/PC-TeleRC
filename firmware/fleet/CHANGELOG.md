# 1.1.0-dev1 — ID-based mission/fleet development

Successor to the manual v1.0.1 node reconnect fix; new TF2 protocol, not an in-place
wire-compatible patch. The existing manual v1.0.1 and Mission 0.2.0rc1 sources are
unchanged.

- Generic rover/node sketches expose only ROVER_ID / NODE_ID per added unit.
- Offline one-time fleet provisioning; future boards reuse fleet credentials.
- Authenticated route discovery removes compiled rover lists, relay counts and
  node order. Supports bounded routes through up to four arbitrary node IDs.
- Idle relay HELLO/ACK proves base readiness without a rover or operator gesture.
- Automatic radio recovery drops pending commands; no auto-arm/mission restart.
- Runtime fleet WATCH list, observed duplicate-ID quarantine and one mission writer.
- Matching TFM1 gateway, read-only fleet monitor and explicit verified AUTO detach
  allow serial deployment of autonomous missions.
- Preserve disarmed upload, full readback, exact rover/digest confirmation, one-shot
  START, actual host/FC heartbeats and conservative fail-closed watchdogs.

Development candidate only. Windows Mission-panel integration and hardware/RF
qualification are outstanding. Address bounds are not a fleet-capacity claim.
