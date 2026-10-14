Current 0.5.0 / 0.1.2rc2 additions: [sketch password, 30-second screen sleep and NODE relays](LILYGO-SKETCH-RELAYS.md). Runtime instructions below remain available with an empty sketch password. Non-empty sketch pairing locks web/USB edits.

# LilyGO T3-S3 runtime setup — firmware 0.4.0 / PC TeleRC 0.1.2rc1

This test candidate adds a BOOT/OLED menu and saved rover Wi-Fi/LoRa selection. BASE remains the native-USB-to-LoRa bridge. It uses TeleRC's existing direct SX1262 pair protocol; it is not Meshtastic firmware and does not communicate with Meshtastic nodes.

## Install once

Disconnect motor power. Flash BASE to the PC-side board and ROVER_WIFI to the rover. ROVER_LORA is the same runtime firmware with LoRa as the initial default. After the first selection, the saved mode overrides either build's default; changing mode no longer requires flashing. Keep flash erase disabled to preserve existing pairing. Install ESP32 core 3.3.2 and RadioLib 7.2.1 if compiling sketches, including for the Wi-Fi default. Select LilyGo T3-S3, SX1262 revision, CDC On Boot enabled and QSPI PSRAM. Keep all adjacent headers with each sketch.

The existing FC UART remains GPIO44 RX / GPIO43 TX, 115200 MAVLink2, ArduRover system 1/component 1. GPIO17/18 drive the onboard SSD1306 OLED. BOOT is GPIO0. The PWM converter remains version 1.0.5 with the pulse glitch fix. The original ESP32 Wi-Fi/ELRS bridge remains 0.1.5.

## BOOT menu

Wait for the firmware to start; holding BOOT during reset selects the ESP ROM downloader instead.

| Action | Result |
|---|---|
| Hold BOOT for 1 second | Pause the link and enter the menu |
| Tap BOOT | Move to the next menu item |
| Hold BOOT for 1 second in the menu | Select the displayed item |
| Select Wi-Fi / LoRa on ROVER | Save the transport and restart |
| Select Link Settings | Start the local configuration Wi-Fi access point |
| Select Status | Show mode, frequency and link status; tap to return |
| Select Exit / Restart | Restart in the current mode |

The data link is paused throughout setup. ROVER sends neutral/release for owned channels; pending UART stop writes retry and block mode changes. BASE stops RF traffic so the rover's existing 500 ms command timeout stops control. There is no automatic transport fallback. A setup restart waits until at least 16 seconds after menu entry and at least 1 second after saving. This exceeds the PC application's maximum 15-second heartbeat timeout, so its previous session latches OFF. Reconnect, center steering, release pedals and manually enable PC Control. ARM remains a separate explicit action. Normal drive watchdogs are unchanged.

## Set the eight-character LoRa password without a PC app

1. On BASE, hold BOOT to enter the menu, tap to Link Settings, then hold to select.
2. Join Wi-Fi **TeleRC-Setup-BASE**, password **telerc123**. Open **http://192.168.4.1**. Use lower-case `telerc123`; the uppercase OLED font labels it PW LOWER. This setup network has no internet.
3. Set the correct LoRa frequency for the hardware and permitted band, power 2–17 dBm, and exactly eight visible ASCII characters. Letters are case sensitive; spaces, Unicode and control characters are rejected. Generate a random password and keep it for the partner board.
4. Save. The board stores the derived pairing key and restarts after the setup pause. Passwords are never read back.
5. Repeat on ROVER using **TeleRC-Setup-ROVER** and the same frequency/password. Select LoRa as its transport. Use the PC application's LilyGO LoRa USB profile with BASE connected by native USB.

BASE has Wi-Fi only for this local setup page. It does not accept driving commands over Wi-Fi or relay Wi-Fi driving traffic to LoRa. ROVER Wi-Fi driving still uses TeleRC-Rover / telerc123, UDP 14550 and CH1/CH2; select the PC Wi-Fi profile when using it. The LoRa password does not change the Wi-Fi passwords.

Opening the menu does not erase existing pairing. The web form requires a password only when saving a new pairing; use the BOOT Wi-Fi/LoRa item to change mode while retaining the current key. Wi-Fi mode also leaves existing LoRa credentials intact.

## Set the same password using PC TeleRC

In PC TeleRC 0.1.2rc1 choose LoRa Setup. Hold BOOT after startup to pause the board, open its native USB port and Read board. Choose **8-character password**, enter the same frequency/password used on its partner, and Save to board. Exit the BOOT menu to restart. For a rover previously in Wi-Fi, select LoRa in its BOOT menu. The password draft stays in memory while pairing the partner; it is cleared when the setup window closes and is never saved in application settings.

Advanced hex key preserves the existing 64-character key workflow. A password is converted to a 32-byte key by PBKDF2-HMAC-SHA256, salt `TeleRC-LoRa-Link-v1`, 10,000 iterations. PC and web setup use identical derivation. Eight-character passwords have less entropy than random 256-bit keys. The existing LoRa protocol authenticates commands; this feature does not add encrypted telemetry.

## Validation

Host checks cover both runtime roles, BOOT debounce/hold/rollover, active Wi-Fi neutral/release, pending-stop backpressure, saved mode, storage failures, setup page validation/CSRF, matching PC/firmware password vectors, delayed restart and OLED failure. Existing controller, Wi-Fi/LoRa arbitration, watchdog and PWM glitch regression checks are retained. Release CI compiles all six ESP32 targets and builds Windows installer/portable packages. This candidate remains a draft; v0.1.1 remains Latest.

Host mocks and target compilation cannot verify the physical OLED, radio, UBEC, button, UART timing or stop latency. With wheels raised and a motor cutoff, verify menu entry stops control, both saved modes survive power cycling, matching passwords connect and a different password cannot drive. Confirm manual neutral enable after exiting setup. Repeat Wi-Fi/LoRa loss, FC heartbeat loss and RC6 takeover tests with USB removed before ground use.
