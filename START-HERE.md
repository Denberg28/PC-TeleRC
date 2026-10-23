# PC TeleRC v0.1.5rc3 candidate

Run PC-TeleRC.exe from a verified Windows portable package. For the source package, use RUN-TELERC.cmd with Python 3.12, or BUILD-WINDOWS-MISSION.cmd to test and create the portable package. Source archives do not contain a prebuilt Windows executable.

## Mission planning

Use **Mission planning** with **TeleRC LoRa Mission 0.2.0rc1** firmware. The package includes public BASE, ROVER, NODE 1 and NODE 2 sketches. Run Mission-firmware/MAKE-MATCHING-SKETCHES.cmd in the portable package, or firmware/mission/MAKE-MATCHING-SKETCHES.cmd in source. Generate one private matching set outside the source folder and flash all participating boards from that set. Public examples have RF disabled.

Plan → connect BASE and rover ID → upload while disarmed → verify full readback → arm using RC → confirm Start. HOLD requires fresh FC confirmation; it does not guarantee physical stopping or accessory OFF. Reconnecting never starts or resumes a mission automatically. Read MISSION-PLANNING.md (under docs/ in source) and complete the firmware HARDWARE_TEST.md before operation.

## Manual driving

Existing manual Wi-Fi, LoRa and ELRS profiles retain their own firmware and setup. Use the existing stable manual installation as rollback. LoRa Mission firmware requires the dedicated mission window and is a separate protocol.

## Offline maps and compact map

Settings → Camera → Open offline map… accepts raster MBTiles. PNG/JPEG/WebP tiles are supported; vector MapLibre offline databases are not. Viewed online tiles also remain cached for offline use. No regional map is bundled. See OFFLINE-MAPS.md for coverage, browsing and offline setup.

Click ▁ in the map bar to minimize it to the lower-left Map button; click Map ▣ to restore.

Driving still requires fresh input, neutral acquisition and manual Enable PC Control. ARM is separate. Confirm link-loss stopping and receiver takeover with wheels raised before ground operation.
