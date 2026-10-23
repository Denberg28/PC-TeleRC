# Windows mission UDP correction — 23 October 2026

The first public Windows run reached all application tests. 281 passed, while
two real UDP peer tests timed out waiting for a fresh FC heartbeat. Firmware
tests and all four actual T3S3 example profiles passed independently.

The pinned pymavlink 2.4.50 UDP constructor binds Windows outgoing sockets to
the remote destination port. On a local peer roundtrip, this misroutes replies
back to the peer's socket instead of the client. It can also collide with another
local listener.

The mission endpoint factory now constructs Windows udpout with local port zero,
then restores the actual remote destination before any MAVLink message is sent.
It retains system/component identity, dialect, target validation, timeouts,
fresh-heartbeat requirements and one-shot mission semantics. Serial, non-Windows
and injected MissionUSB transports are unchanged. No firmware source changed.

PASS locally: two real UDP mission roundtrips and five endpoint regressions,
including invalid remote ports and the actual local/remote port separation.
The native Windows workflow must rerun the complete application/frozen/package
gates from this corrected source before publication. Hardware qualification and
the existing single-active-radio-session limit remain unchanged.

The next Windows run passed the real UDP peer checks. Its remaining failure was
the source-parity guard comparing desktop endpoint construction with the immutable
firmware CLI. The guard now normalizes only that exact factory call back to the
original connection expression; every other initializer and transaction AST stays
under the original exact comparison. The endpoint factory has separate regression
coverage. The firmware CLI and public firmware manifest remain byte-for-byte intact.
