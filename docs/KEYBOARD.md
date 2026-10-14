# Keyboard driving

1. Choose **Keyboard — WASD / arrows** under Driving Input, then **Apply Settings**.
2. Connect to the rover as usual. Keyboard works through the existing Wi-Fi, LilyGO LoRa and experimental ELRS USB profiles; a wheel is unnecessary in keyboard mode.
3. Click the keyboard driving area. Release every driving key. Enable PC Control manually; ARM remains a separate action.

| Key | Command |
| --- | --- |
| W / Up arrow | Forward |
| S / Down arrow | Reverse |
| A / Left arrow | Steer left |
| D / Right arrow | Steer right |
| Hold Space | Brake command: neutral steering and drive |

Release keys to return their axis to neutral. Forward/reverse and left/right pairs cancel each other; combining a steering key with a drive key permits a turn. Steering sensitivity, drive sensitivity and throttle limit still apply. Keyboard commands are digital; these settings cap their magnitude.

Space takes priority over every driving key. A direction held before or during braking remains suppressed after Space is released. Release and press that direction again to move. Space sends neutral at the existing radio cadence; physical stopping distance and coast/brake behavior depend on ArduRover, the PWM converter, motor drivers and terrain. It does not command reverse torque or disarm.

Driving keys work only while the keyboard driving area has focus. Typing in settings never drives. Changing focus, minimizing, switching apps or opening a dialog stops keyboard control and clears held keys. Returning to the app never enables control automatically. After a stop, click the driving area, release keys and manually enable again.

Input-source and settings changes disable control. Fresh input, neutral acquisition, heartbeat/remote-status gates, controller-session checks and existing stale-input fail-safes remain active. A stopped GUI event loop makes keyboard samples stale; recovery changes the input session and blocks previous held directions. Wheel acquisition still runs independently of the GUI refresh timer.

This is an unsigned test candidate. Software checks cover key combinations, repeat events, brake priority, focus loss, stale input, source changes and existing regression cases. Physical rover braking and fail-safe timing require hardware testing. Existing v0.1.2rc2 firmware remains compatible; no sketch update is needed for keyboard input.
