Current candidate 0.1.2rc2 / LilyGO 0.5.0: edit .ino password/frequency/relay count before upload. NODE indices 1/2 form an ordered chain. 30-second OLED timeout and BOOT wake. Read docs/LILYGO-SKETCH-RELAYS.md. New runner: python3 firmware/relay-tests/run_tests.py.

Candidate v0.1.2rc1: LilyGO runtime Wi-Fi/LoRa 0.4.0 with BOOT/OLED setup, PWM converter 1.0.5 and original bridge 0.1.5. See docs/LILYGO-RUNTIME-SETUP.md.

Host checks: python3 firmware/runtime-tests/run_tests.py, plus the three existing runners below.

Stable v0.1.1: LilyGO Wi-Fi/LoRa 0.3.1, PWM converter 1.0.5, original Wi-Fi/ELRS bridge 0.1.5.

Read ../docs/STABLE-v0.1.1.md for transport/board selection and ../docs/LILYGO-WIFI-LORA.md for LED, UART and power setup. PWM noise investigation: ../docs/FIRMWARE-RECOVERY-rc7.md.

Host checks from repository root: python3 firmware/tests/run_tests.py; python3 firmware/lora-tests/run_tests.py; python3 firmware/lilygo-tests/run_host_tests.py. Release CI compiles six targets before stable publication. Physical hardware testing remains outstanding.
