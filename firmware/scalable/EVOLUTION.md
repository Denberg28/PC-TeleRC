# Scalable system path

0.4.0rc1 implements the bounded foundation: saved project identity, incremental
board issuance, full BASE endpoint key table, node IDs independent of path position,
read-only on-demand discovery, selected source routes, fresh command admission,
manual airtime budgeting and no watchdog relaxation.

The next acceptance gate is physical qualification: latency/collision measurements
for direct and two-relay links, later-node recovery, increasing radio density,
receiver takeover and measured stop timing. Advertise capacity from those results.

Deeper mission-only paths require a separate protocol/PC capability revision and
an explicit latency policy; they must not silently inherit manual driving approval.
Multi-rover manual selection needs identity/session locking, settings and transport
changes on PC. Simultaneous monitoring needs a scheduled airtime budget per rover.
Neither is implied by a larger address space.

Per-device revocation, duplicate-device RF diagnostics and field key rotation are
separate enrollment/management work. Keep the shared route-key threat model explicit;
relay compromise can deny service even though endpoint commands remain encrypted.
Maintain immutable versioned rollback packages through each migration.
