# PC TeleRC camera desktop — v0.1.2

The driving screen places live video in the center, the rover map at the lower left, compact control buttons below the view and three always-visible percentage sliders: steering sensitivity, drive sensitivity and throttle limit. Settings opens a collapsible Link / Input / Camera panel. The title bar and Windows executable use the exact TeleRC Android logo.

## Camera setup

Open **Settings → Camera**, choose the source and click **Start**:

- **USB camera:** connect a webcam or video capture device to the PC, click Refresh and select it.
- **RTSP / HTTP video:** enter the camera's supported stream URL, such as `rtsp://192.168.1.20:8554/live`. H.264 playback is verified with the packaged Qt/FFmpeg backend; actual camera/server compatibility depends on its stream format.
- **HTTP MJPEG:** select this for an ESP32-CAM or similar JPEG stream, such as `http://192.168.1.20:81/stream`.

Camera starts only on request. Stop closes its camera/network resources. USB disconnects, network errors and stalled video display an unavailable/stale state. A retained frame is visibly dimmed after 1.5 seconds without a decoded update. Camera operation never arms, enables, reconnects or supplies driving input.

Video needs a separate USB or Wi-Fi/network connection. The LilyGO SX1262 LoRa link carries control and compact telemetry, not video. A PC connected only to TeleRC-Rover Wi-Fi can access a camera only when that camera is reachable on the same network or another PC interface. No camera device is bundled or assumed.

Stream user/password credentials and query tokens are used only for the current connection; they are removed from the saved URL. Re-enter them after restarting the app if required. Backend errors shown in the UI do not expose a camera URL.

## Map and telemetry

The map accepts GPS_RAW_INT and GLOBAL_POSITION_INT only from the locked autopilot. A confirmed 3D GPS fix and a position received within five seconds are required for the live marker. It displays the measured route, available heading and a yellow marker for the first accepted session position. That marker is a display reference, not an uploaded flight-controller home or return command. It never invents motion from wheel/key commands.

Zoom uses the lower-left +/− buttons. The map follows accepted rover positions. Without GPS data it says **Waiting for rover GPS**. A lost fix/link or stale position changes the marker/status; it does not present a stale point as live.

Online OpenStreetMap tiles need internet. Turn them off under Camera settings when internet is unavailable or undesired; the GPS track still works. Only visible tiles are requested, with at most four requests active, application identification, seven-day local caching, conditional refresh and visible attribution. No map-area prefetch/download feature is provided.

If the FC has GPS but no position reaches the app, use Mission Planner to inspect the stream rates for the bridge's MAVLink port. ArduPilot's extended-status stream includes GPS_RAW_INT/SYS_STATUS; its position stream includes GLOBAL_POSITION_INT. On ArduRover 4.6.3 these are `SRx_EXT_STAT` and `SRx_POSITION`; `x` identifies the MAVLink channel and need not equal the physical SERIAL number. Keep rates modest on LoRa. Existing bridge command whitelists remain unchanged, so PC TeleRC does not bypass them to modify stream rates.

References: [ArduPilot telemetry streams](https://ardupilot.org/dev/docs/mavlink-requesting-data.html), [Qt video](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/index.html), [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Controls

Wheel and keyboard remain selectable at the top. Keyboard uses WASD or arrows, with Space sending neutral brake. Click the camera area to focus keyboard driving. All driving keys must be released before enable/ARM. Opening settings, moving keyboard focus away or switching apps disables active keyboard control; return and enable manually. Camera loss alone does not change wheel/control ownership.

Moving a sensitivity/limit slider disables control and creates pending settings. Apply under **Settings → Input**, then manually re-enable at neutral. Displayed percentages reflect the pending slider value; control does not silently adopt edits while active. ARM/DISARM remain separate explicit actions.

Stable describes the packaged software release. Real rover braking, USB camera hardware, a user's network stream, radio range and physical fail-safe timing still require hardware checks. No firmware upload is needed for this UI change. The release includes the unchanged source-matched LilyGO 0.5.0/PWM firmware and verified target binaries for users who need the earlier firmware updates.
