Stable v0.1.1: LilyGO Wi-Fi/LoRa 0.3.1, PWM converter 1.0.5, original Wi-Fi/ELRS bridge 0.1.5.

Read ../docs/STABLE-v0.1.1.md for transport/board selection and ../docs/LILYGO-WIFI-LORA.md for LED, UART and power setup. PWM noise investigation: ../docs/FIRMWARE-RECOVERY-rc7.md.

Host checks from repository root: python3 firmware/tests/run_tests.py; python3 firmware/lora-tests/run_tests.py; python3 firmware/lilygo-tests/run_host_tests.py. Release CI compiles six targets before stable publication. Physical hardware testing remains outstanding.
