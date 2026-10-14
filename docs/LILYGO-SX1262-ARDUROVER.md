Current runtime candidate 0.4.0: see [BOOT/menu and password setup](LILYGO-RUNTIME-SETUP.md). The wiring and protocol notes below remain applicable; the new menu replaces older re-pairing/compile-time mode instructions.

# LilyGO T3-S3 SX1262 ArduRover direct pair — firmware 0.2.0 / PC 0.1.1rc5

Use two matching T3-S3 SX1262 boards: BASE connected to the Windows PC by native USB; ROVER connected to SpeedyBee UART3. This removes Wi-Fi from the driving path. The external SX1262 antenna belongs to LoRa; it does not boost the ESP32 Wi-Fi radio. Attach the correct band antenna to both boards before enabling RF.

This is a direct pair. Both boards need this firmware. It does not interoperate with Meshtastic, the older TeleRC mesh firmware, or ordinary ELRS/CRSF. The older mesh work remains under `bridge/TeleRCMesh` in the repository. No relay is needed for the first test.

## Wiring

Keep the existing ESP32-S3 PWM converter connected to M5–M8 and the four BTS7960 drivers. Replace only the Wi-Fi bridge at UART3. Disconnect the old bridge TX/RX; never connect two bridge transmitters to FC R3.

| Rover connection | LilyGO T3-S3 |
|---|---|
| FC T3 / UART3 TX | GPIO44 / UART RX |
| FC R3 / UART3 RX | GPIO43 / UART TX |
| Logic supply 5 V | 5 V input |
| FC/logic ground | GND |

GPIO43/44 are 3.3 V UART signals. Do not put 5 V on these GPIOs. The internal SX1262 uses SCK5, MISO3, MOSI6, CS7, RESET8, DIO1=33, BUSY34. These are already wired on the supported T3-S3 SX1262 V1.2/V1.3 board. Do not reuse them for motor signals. This build does not support other LilyGO variants.

BASE: native USB cable to the PC; no FC wiring. ROVER: retain a suitable regulated logic supply and common signal ground; motor power stays on its existing path. USB can mask supply dips during testing. Avoid paralleling independent 5 V supplies. GPIO43/44 are unavailable for FC wiring if a UART0 adapter is using them; use the board's native USB.

FC parameters: retain `SERIAL3_PROTOCOL=2`, `SERIAL3_BAUD=115`, `MAV_GCS_SYSID=255`, CH1 steering / CH2 throttle. The radio firmware expects FC system 1/component 1. Retain `RC6_OPTION=46` and existing transmitter takeover wiring. PC/LoRa never overrides CH3–CH8. Mode is MANUAL for this candidate. The release does not import any FC parameters or change motor mapping. The saved `BASE.param` is historical, not a read of your current FC.

## Flash and pair

1. Disconnect motor power. In Arduino IDE install ESP32 core **3.3.2** and RadioLib **7.2.1**. Select **LilyGo T3-S3**, radio revision **SX1262**, USB CDC On Boot **Enabled**, and PSRAM **Enabled**. Use the board's native USB COM port.
2. Flash `firmware/TeleRCLoRa_BASE/TeleRCLoRa_BASE.ino` onto the PC board. Flash `firmware/TeleRCLoRa_ROVER/TeleRCLoRa_ROVER.ino` onto the rover board. Keep the three adjacent headers in each sketch folder. Blank boards start with RF disabled.
3. Open PC TeleRC **0.1.1rc5**, go to **LoRa Setup**, choose the connected BASE COM port and click **Open USB / Read board**. Its profile must say **BASE / SX1262 / ARDUROVER** and radio inactive.
4. Enter the frequency matching both radio/antenna labels and your permitted operating band. There is no automatic 433/868/915 MHz guess. Start at **2 dBm** for the close-range bench test. Click **Generate** once to create a 64-character pairing key, then **Save to board**. Keep this window open: the pairing draft remains in memory.
5. Close USB. Connect the ROVER, read it, and save the same frequency, power and key. Check that its role is ROVER. Restart both boards physically. The readout should show active radios and the same fingerprint. No secret is read back or placed in diagnostic reports/settings files.
6. To re-pair an already active board, disconnect motor power, hold BOOT for at least one second **after the sketch is running**, release it, then read/provision the inactive board in LoRa Setup. Do not hold BOOT during RESET; that enters the ESP download bootloader. RF remains disabled until a physical restart. The generic app rejection text also permits erasing NVS; holding BOOT after startup is sufficient for this firmware.
7. Close the setup USB session, connect the BASE to the PC and choose **LilyGO T3S3 SX1262 LoRa USB** in the connection dropdown. Select the BASE COM port, then Apply & Reconnect. Wait for the real FC heartbeat, MANUAL and fresh rover status.
8. Center the wheel, release pedals and manually enable PC Control. Neutral commands are sent during acquisition; motion waits for authenticated rover ownership. ARM remains an explicit separate action. No automatic ARM or control enable is added.

Prebuilt binaries in the release were compiled for the exact board options above. The `.ino` folders are the clearest Arduino IDE upload route. Raw `.bin` flashing requires the matching offsets from the included build metadata; do not guess offsets or flash a BASE image to the ROVER.

## Link behavior

- Native CDC: 115200 baud, DTR high, RTS low; CRC16-framed datagrams match the existing PC transport.
- SX1262: SF7 / BW500 kHz / CR4:5 / preamble8 / TCXO1.6 V; boosted receive gain. CAD precedes every transmit. Higher spreading factors are not supported by this timing profile.
- Latest commands replace queued axis values. Host commands older than 200 ms are discarded. No replay of a buffered movement burst after reconnect.
- Authenticated packets use HMAC-SHA256 truncated to 128 bits. A rover-generated random 64-bit challenge permits one command response within 90 ms. The pairing key authenticates packets; this is not encrypted telemetry.
- PC samples/sends LoRa commands at 10 Hz. Rover polling has a 100 ms spacing after poll completion; airtime and CAD reduce actual RF command updates, typically below 10 Hz. This is slower than the local 20 Hz Wi-Fi send path. No range or real latency guarantee is claimed.
- A motor axis without an accepted command for 500 ms stops/releases CH1/CH2 and requires neutral acquisition. FC heartbeat loss at 2.5 seconds, UART short writes and radio faults also stop owned control. Monitor-only operation sends no generated overrides to the FC.
- Every rover poll carries authenticated ownership, boot ID, stop count and cause. A new stop, reboot, lost ownership or 500 ms of missing rover status latches PC Control OFF. Recovery requires manual re-enable at neutral. The underlying PWM converter retains its existing 150 ms PWM timeout / 300 ms neutral dwell.
- No synthetic FC heartbeat: armed/mode state comes from ArduRover. Limited heartbeat, command ACK, status/GPS/position and STATUSTEXT telemetry avoids filling the control channel. Firmware queues and work per loop are bounded; stopped USB output does not block the rover's watchdog.
- Transmitter takeover remains FC-controlled via RC6. Neutral/release after link loss permits the FC to use the receiver; actual takeover and physical stop behavior require a bench test.

## Acceptance test

First test with wheels clear, low throttle and a reachable motor-power cutoff. Confirm physical direction and left/right motor mapping. Repeat rapid steer/drive commands, then disconnect BASE USB and verify prompt stop. Reconnect: PC control must remain off until manually enabled at neutral. Repeat rover radio power loss, FC UART disconnection, RC6 transmitter takeover and a second cold start. Record `Radio` in Copy Report, app stop reasons and converter USB logs.

After these pass, compare low-speed ground runs with Wi-Fi using the same route, throttle setting, antenna placement and power arrangement. Log stops per run. A failure with LoRa and Wi-Fi under load still points toward the shared FC/PWM/power path. This build does not establish or cure the earlier ground/bump fault without that comparison.

## Sources

- LILYGO pin map and board selection: https://wiki.lilygo.cc/products/t3-series/t3-s3-v1.3/
- Official SX1262 setup: https://github.com/Xinyuan-LilyGO/LilyGo-LoRa-Series/blob/master/docs/en/t3_s3_sx1262/t3_s3_sx1262_hw.md
- ArduPilot MAVLink RC override behavior: https://ardupilot.org/dev/docs/mavlink-rcinput.html
- RadioLib: https://github.com/jgromes/RadioLib
