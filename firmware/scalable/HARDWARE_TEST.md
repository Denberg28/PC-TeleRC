# Physical qualification — not passed by host tests or compilation

Record the actual board/FC/app/firmware versions, private project identifier,
radio parameters, antenna layout, topology and measured worst-case timings.
Use restrained wheels, low authority and an independent local cutoff.

1. Migrate the whole matched TU2 network. Check real FC heartbeat, FC system ID,
   UART wiring and channel direction. Confirm public examples stay RF OFF.
2. Test direct, NODE3 alone, NODE200 alone and NODE3 → NODE200. Verify the displayed
   route qualification and actual path; nodes outside the path may stay standby.
3. Add NODE4 from the saved project and power it later without reflashing BASE,
   ROVER or other nodes. Break the existing path and confirm recovery through it.
4. Confirm a three-relay serial chain is refused. Never raise watchdogs to make
   a route pass. Verify a slow two-relay path blocks manual command admission.
5. Measure stopped/neutral acquisition, non-neutral ARM refusal, explicit ARM,
   per-axis sparse freshness and actual stop/release on USB/RF/input/UART/FC loss.
   Verify manual control stays off until deliberate neutral re-enable.
6. Inject node/BASE/ROVER reboot, power ripple and interference. Lost work must
   not replay; a route recovery must invalidate mission upload/start verification.
7. Run short disarmed upload/readback tests, independent RC arm, one-shot Start,
   HOLD and lost-ACK UNKNOWN tests on every intended route. Confirm no auto-arm.
8. Increase nearby/hidden node count gradually. Measure discovery success/time,
   collision load, telemetry age, manual latency, recovery and GCS-loss behavior.
   Publish only measured capacity at the tested settings; 200 IDs is not capacity.
9. Inspect the saved device inventory for duplicate IDs before deployment. Test
   replacement only after powering off/retiring the old board. Do not assume RF
   duplicate-identity detection; provisioning prevents duplicate issuance only.
10. Independently verify ArduRover AUTO continuation/takeover policy and every
    auxiliary OFF event. Stop testing on unexpected motion.

Do not promote this candidate to stable until these results are recorded.
