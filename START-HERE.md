# PC TeleRC v0.1.3

Use PC-TeleRC.exe from the portable package or install PC-TeleRC-Setup-v0.1.3.exe.

## Your working LoRa setup

Keep your existing 915 MHz / telerc123 BASE and ROVER firmware. Select LilyGO T3S3 SX1262 · LoRa and BASE's actual COM port, then Apply Connect. If LoRa setup has the port open, click Close USB first and close that window. The compiled preset needs no Save to board step. The included preset sketches/target builds are for reinstallation only; no reflash is required for the map update.

## Offline maps and compact map

Settings → Camera → Open offline map… accepts raster MBTiles. PNG/JPEG/WebP tiles are supported; vector MapLibre offline databases are not. Viewed online tiles also remain cached for offline use. No regional map is bundled. See OFFLINE-MAPS.md for coverage, browsing and offline setup.

Click ▁ in the map bar to minimize it to the lower-left Map button; click Map ▣ to restore.

Driving still requires fresh input, neutral acquisition and manual Enable PC Control. ARM is separate. Confirm link-loss stopping and receiver takeover with wheels raised before ground operation.
