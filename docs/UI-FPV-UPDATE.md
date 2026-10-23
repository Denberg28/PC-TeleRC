# PC TeleRC FPV interface update

Based on `release/publish-v1.0.0` at `7b555bf1419587afb8932bbb3f145f31a11b5770`.

The separate health row and telemetry cards above the camera are replaced by
transparent, shadowed readings at the upper right of the main camera/map view.
The overlay passes mouse events through to the view. Detailed connection and
channel readings remain available in Settings. Mission and view buttons use
short labels; the minimized-map button reads `Map` without a font-dependent glyph.
Camera instructions wrap within the inset.

The map opens at TeleRC's display-only starting location (13.6218, 123.1948),
or the saved map view. This does not create a rover position, home or track.
Loading prioritizes central coverage and retains cached lower-detail coverage
when zooming in. Online loading and offline missing-coverage messages are distinct.
The Qt reply-header call is corrected so successful map replies finish caching;
initial HTTPS loading has a longer display-only timeout and transient retries.
The desktop continues using its existing native raster map and raster MBTiles.

The green icon uses the TeleRC Go launcher geometry from
`Denberg28/telerc_go`, `go/src/main/res/mipmap-anydpi/go_launcher.xml`, blob
`8f4e2fd2ca8c92f02a56f70546b4b8830ae2b834`, with stroke `#16A34A`.
PNG and multi-size ICO assets serve the header, window and existing installer paths.

Validation on Linux with Qt 6.11.2: the initial FPV changes passed 31 focused
camera, map, icon and UI checks. The selector/spacing refinement passed 22 focused
UI and keyboard checks, including each WASD and arrow-key direction.
The new HTTP map test uses a local fixture server and verifies complete coverage,
cache metadata and the four-request bound. Fresh/stale readings, transparent input
pass-through, swap/minimize and radio-state invariance are covered.
Selectors use WIFI / LORA and Steering Wheel / Keyboard, with equal widths and
aligned Connection / Controls labels. Main buttons and slider groups use uniform
sizing and spacing. Visual checks at 1180×720 and 900×580 show 58 px more view
height than the original layout: 449→507 px and 309→367 px respectively. Live online map loading was also checked.

Only display/media files, icon assets and related tests changed. No firmware,
radio/control worker, mission protocol or fail-safe logic changed. This initial source UI review predates v1.0.1 release packaging; see
docs/releases/v1.0.1.md and its workflow evidence for current release status.
