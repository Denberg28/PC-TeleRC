Candidate: Wi-Fi/ELRS bridge 0.1.5, PWM converter 1.0.5, SX1262 direct pair 0.2.1.

Read ../docs/FIRMWARE-RECOVERY-rc7.md for the reproduced PWM noise defect, flashing roles, validation, and remaining hardware checks.

Host checks: python3 firmware/tests/run_tests.py and python3 firmware/lora-tests/run_tests.py from repository root. Actual Arduino target builds for all five role/mode targets are required by CI.
