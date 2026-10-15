# LoRa USB setup — PC TeleRC 0.1.3rc1

## Connect an already paired or compiled-password preset

Use one LilyGO T3-S3 SX1262 BASE at the PC and one matching ROVER at the vehicle. With no intermediate NODE, both firmware profiles must use relay count 0. Both boards must have the same frequency and derived pairing key. Use the correct frequency/antenna for the board variant.

1. Connect BASE by its native USB data port. Windows may identify the ESP32-S3 as USB JTAG/serial debug unit; select its serial COM entry under Ports (COM & LPT).
2. Close Arduino Serial Monitor, Mission Planner and other applications using that COM port.
3. Exit BOOT/setup menus on both boards. Select LoRa on ROVER. A saved Wi-Fi selection overrides the ordinary sketch's initial mode; the supplied pnp915-1 preset migrates that selection on its first boot.
4. In PC TeleRC choose LilyGO T3S3 SX1262 / LoRa, refresh ports, select BASE's actual COM number and Apply & Connect. COM numbers can change after upload/reconnection.
5. The app verifies the BASE's USB identity and active radio, then waits for the actual rover heartbeat. USB opened, BASE verified and rover heartbeat received are distinct states. No heartbeat is synthesized.
6. Keep the working FC UART wiring and parameters. LilyGO GPIO44 RX receives FC T3; GPIO43 TX drives FC R3; common ground; UART3 MAVLink2 at 115200. GPIO17/18 are OLED pins.
7. After a fresh heartbeat and neutral input, manually enable control. ArduRover requires MANUAL mode. ARM is separate and explicit.

Compiled-password presets need no PC pairing entry. A nonempty password in the sketch overrides saved pairing on every boot and locks web/USB pairing writes. Change both sketches and upload both boards to change that pairing. `telerc123` contains **nine** characters; pnp915-1 supports the complete value. Older eight-character-only sketches reject it at compilation.

## Configure boards that use saved pairing

Disconnect motor power. Open LoRa setup from the main window's LoRa connection settings. Configure one board at a time:

1. Hold BOOT after startup to pause supported firmware. If the OLED is asleep, the first complete press only wakes it; release and hold again to enter setup.
2. Select its COM port and Open USB. Opening setup USB stops the driving link first.
3. Read board. Frequency is an editable field in this window, in **MHz**: for example `915.000` on appropriate 915 MHz hardware. Do not enter `915000` here; that unit is kHz in the sketch.
4. A reported zero frequency means no valid pairing frequency is configured. The field is cleared so a previous board's value cannot be mistaken for this board's saved setting.
5. Enter an 8–32-character visible ASCII password without spaces, or use Advanced hex key. The app derives the key with PBKDF2-HMAC-SHA256, salt `TeleRC-LoRa-Link-v1`, 10,000 iterations, preserving existing eight-character vectors. Only the derived 32-byte key is sent over the existing USB setup protocol. Older saved-pairing firmware accepts that derived hex key; it does not need to accept the raw password in its own web editor.
6. Save, Close USB and exit the BOOT setup menu/restart. Repeat on the partner using the same frequency/password. Draft credentials remain in memory for the partner and clear when the dialog closes; credentials are not saved in AppSettings.
7. Close the setup dialog before Apply & Connect. A failed close blocks reconnection so two app paths cannot open the same selected USB port.

## Failure messages

| Message | Meaning and next step |
| --- | --- |
| Access denied or port busy | Close serial applications. Another process or Windows permissions may prevent access. |
| Port not found | Replug, refresh and select the COM number that appears in Device Manager. |
| Device unavailable | Check the data cable, USB connection and serial driver. Reconnect manually. |
| No TeleRC LoRa board reply | Port opened, but the firmware did not return the expected framed reply; check board role, firmware, normal boot and native USB. |
| BASE unconfigured / 0 MHz | Configure matching saved pairing or upload a matching compiled preset. |
| BASE radio inactive | Exit setup and restart; if it persists, check the SX1262 firmware/radio. |
| BASE USB verified, waiting for rover heartbeat | USB and BASE checks passed; check ROVER LoRa mode, frequency/key/relay count, RF path and FC UART. |
| Pairing defined in sketch | Saved pairing cannot override compiled settings. Edit and upload both sketches. |

Raw serial-driver exception buffers are not shown or logged by the connection/setup error handler. USB write success alone does not prove radio delivery. The application cannot resolve an external Windows COM-port lock. Physical RF range and stop timing require hardware validation.
