# TeleRC M5–M8 to four BTS7960 drivers
Target: ESP32-S3 DevKitC-1. This package configures the existing TeleRC converter for FOUR required PWM inputs (TELERC_PWM_PAIRED=0). It is a PWM-only converter; retain the separate Wi-Fi/LoRa gateway.

## Arduino upload
Open TeleRC_M5_M8_Converter/TeleRC_M5_M8_Converter.ino. Select ESP32S3 Dev Module and the flash/PSRAM settings of your board. ESP32 Arduino core 3.3.2 is the repository CI baseline. No extra libraries are required. Serial Monitor: 115200 baud.
This package was configured and inspected, but not compiled or tested on hardware in this session.

## FC inputs and motor outputs
| SpeedyBee signal | ESP input | Wheel | ESP RPWM | ESP LPWM |
|---|---|---|---|---|
| M5 | GPIO4 | Front left | GPIO8 | GPIO9 |
| M6 | GPIO5 | Rear left | GPIO10 | GPIO11 |
| M7 | GPIO6 | Front right | GPIO12 | GPIO13 |
| M8 | GPIO7 | Rear right | GPIO14 | GPIO15 |

GPIO numbers are NOT header position numbers.
M5–M8 are signal pads, not motor power. Confirm signal high level is suitable for 3.3V ESP inputs. Never apply 5V to ESP GPIO.

## ArduRover settings
For the mapping above:
SERVO5_FUNCTION=73 (Throttle Left)
SERVO6_FUNCTION=73 (Throttle Left)
SERVO7_FUNCTION=74 (Throttle Right)
SERVO8_FUNCTION=74 (Throttle Right)
For SERVO5 through SERVO8: MIN=1000, TRIM=1500, MAX=2000.
MOT_PWM_TYPE=0 (Normal RC servo PWM), SERVO_RATE=50.
Review existing SERVOx_REVERSED before testing. Do not blindly overwrite it.
Reboot after changing output protocol. Check actual outputs: center 1500us, reverse toward 1000us, forward toward 2000us.
The ESP generates the 20kHz power-stage PWM. FC outputs must remain 1000–2000us servo pulses; do not select DShot or brushed duty PWM.
Existing RC channel mapping is separate from SERVO output assignments.

## Each BTS7960 / IBT-2
| BTS connection | Destination |
|---|---|
| RPWM | Assigned ESP RPWM, through 3.3V-to-5V buffer if required |
| LPWM | Assigned ESP LPWM, through 3.3V-to-5V buffer if required |
| VCC | Regulated 5V logic supply |
| R_EN and L_EN | Regulated 5V logic supply |
| GND | Common signal ground |
| B+ | Motor battery positive through fuse/cutoff |
| B- | Motor battery negative, using motor-rated return wire |
| M+ and M- | That wheel motor |
| R_IS and L_IS | Leave unconnected |

Use a common ground between F405, ESP, UBEC and all drivers. Motor return current must go through power wiring, not FC/ESP ground leads.
Power ESP through its documented 5V/VIN input from the regulated UBEC. Do not connect raw 2S voltage to ESP or driver VCC. Avoid USB and external 5V simultaneously unless the carrier permits it.

### Logic compatibility and reset
IBT-2 modules differ. Do not assume a 5V-powered module accepts 3.3V logic. For unverified modules, use TWO SN74AHCT125 buffers (eight PWM channels): VCC=5V, GND=common, each active-low OE tied to ground, each A from ESP GPIO and each Y to the corresponding driver PWM input. Add 100nF supply decoupling at each buffer. Do not substitute 74HC125/74AHC125 without verifying their thresholds.
Use 10k pulldowns on all eight ESP PWM lines (buffer A inputs), and on driver PWM inputs if they can become disconnected/floating. If direct 3.3V drive is confirmed compatible, put pulldowns on driver PWM inputs.
Tied-high enables mean software cannot independently disable the bridges. Both PWM low is a zero-command state; it may electrically brake rather than coast. Provide a physical motor battery cutoff.

## Behavior and first test
Input neutral band: 1500us +/-35us. At boot or after a PWM fault, all four inputs must remain valid and neutral for 300ms before motion is accepted.
Loss/invalidity of any required input sets every motor command to zero; missing pulses time out at 150ms plus the next nominal 5ms control iteration.
Acceleration slew and reversal through zero are retained. Default MAX_MOTOR_DUTY=255. For first powered tests change it to 128 (about 50% PWM duty); this is not a steering-only limit or a guarantee of half speed/current.
1. Disconnect motor battery. Verify wiring, levels and FC output pulses.
2. Raise/restrain wheels; use current-limited power if available and keep cutoff accessible.
3. Verify neutral boot and non-neutral boot inhibition.
4. Test each wheel and turn direction at low command. Correct using motor wire reversal or INVERT_MOTOR in FL, RL, FR, RR order.
5. Disconnect M5, M6, M7 and M8 one at a time: every motor command must go to zero. Verify recovery requires neutral.
6. Verify FC disarm and loss of app/RC control: converter cannot detect a lost command link if FC continues valid non-neutral PWM. FC link/RC failsafes remain essential.

Source: https://github.com/denberg28/TeleRC/tree/main/bridge/BTS7960PWMConverter

