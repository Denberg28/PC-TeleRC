# PC TeleRC v1.0.1

Run PC-TeleRC.exe from the portable folder, or use the Windows installer. Source
users need Python 3.12 and BUILD-WINDOWS-MISSION.cmd to build an executable.

Select WIFI or LORA, then Steering Wheel or Keyboard. Keyboard accepts WASD and
arrow keys while the camera has focus; hold Space for neutral. Apply settings
before enabling PC Control at neutral. Camera and map controls do not acquire
driving authority. Open Settings for radio, camera and calibration details.

Read FIRMWARE-COMPATIBILITY.md (docs/FIRMWARE-COMPATIBILITY-v1.0.1.md in source)
before flashing. Manual-firmware contains the reviewed LoRa v1.0.1 BASE, ROVER,
NODE1 and NODE2 package. It supports manual driving. Mission-firmware contains
separate LoRa Mission 0.2.0rc1 sketches and MAKE-MATCHING-SKETCHES.cmd; generate a
private matching set outside the source folder before using Mission. Public TM2
examples have RF OFF. Do not mix manual and mission board roles.

Mission: plan → connect BASE and rover ID → upload disarmed → verify readback →
arm with RC → confirm Start. Reconnection never starts or resumes automatically.
Use MISSION-PLANNING.md for commissioning. Only one mission session is active.

Settings → Camera → Open offline map accepts raster MBTiles. Viewed online maps
remain cached; no regional map is bundled. The lower-left Map button restores the
minimized map. The default map view is not a measured rover position.

Back up settings, FC parameters and private provisioning. Separate images in the
new firmware bundle preserve NVS without erase; older factory images erase all
flash/NVS. Keep the previous matching app/firmware set. Physical RF, stop timing,
power and takeover qualification remain unrecorded; complete restrained checks
and retain a local cutoff before operation.
