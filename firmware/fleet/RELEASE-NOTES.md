Development successor to the manual LoRa v1.0.1 reconnect fix. New TF2 protocol,
added separately under firmware/fleet; original manual/Mission firmware unchanged.

Adding a unit requires editing only ROVER_ID (1..20) or NODE_ID (1..200) in that
unit's private sketch, reusing one-time fleet credentials. Existing boards do not
need a new fleet list, relay count, node order, or per-rover key table. Each FC's
SYSID_THISMAV must match its rover ID.

Includes automatic bounded route discovery (0..4 relays), idle node HELLO/ACK
readiness, radio recovery without command replay, duplicate-ID conflict detection,
matching host tools, read-only fleet monitor, one mission writer and explicitly
verified AUTO-continuation detach for serial autonomous deployments.

Preserves disarmed upload, complete readback, exact rover/digest confirmation,
one-shot START and no radio arm/RC/parameter writes. Never synthesizes GCS/FC
heartbeats. Sharing ENDPOINT_ROOT permits ID-only expansion but shares endpoint
trust: compromise of one rover compromises the fleet root. Nodes hold routing
keys only. No individual endpoint revocation without reprovisioning.

NOT compatible with the released Windows Mission panel (TM2), manual v1.0.1/v4,
or Mission 0.2.0rc1/TM1. Upgrade the participating firmware once and use the matching
TFM1 gateway/CLI. Address/path bounds are not simultaneous RF capacity claims.
One active writer; no simultaneous fleet command control.

Candidate remains DRAFT pending Windows integration, radios/vehicles/HIL, measured
loss/failover timing and RF-capacity qualification. Automated host/runtime tests
and real ESP32 target compilation are recorded; no hardware qualification claimed.
No private credentials or provisioned binaries are included. Existing stable
release assets and Latest are unchanged.
