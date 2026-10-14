# PC TeleRC 0.1.2rc3

Keyboard: select **Keyboard — WASD / arrows**, Apply Settings, click the driving area, release all keys and manually enable PC Control. W/Up forward, S/Down reverse, A/Left and D/Right steer; hold Space for neutral brake. See KEYBOARD.md in the portable build or docs/KEYBOARD.md in source. Focus loss stops control. No firmware update is required for keyboard input.

Read docs/LILYGO-SKETCH-RELAYS.md. Edit password/frequency and matching relay count at the top of BASE, ROVER and NODE sketches before uploading. NODE index 1 is nearest BASE; index 2 nearest ROVER. OLED sleeps after 30 seconds; the first BOOT press wakes only. A second hold enters setup and stops PC control. Manual enable/ARM at neutral remain separate. Hardware testing required. v0.1.1 remains stable.

