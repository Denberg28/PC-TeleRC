#!/usr/bin/env python3
"""Compile every generated profile with the Arduino CLI; never flashes boards."""

import argparse
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profiles", type=Path)
    p.add_argument("--cli", default="arduino-cli")
    a = p.parse_args()
    profiles = sorted(a.profiles.glob("TeleRCMission_*"))
    if not profiles:
        p.error("No generated profiles found")
    # Manufacturer profile: standard 4 MB T3-S3, SX1262 revision, no PSRAM.
    fqbn = "esp32:esp32:lilygo_t3s3:Revision=Radio_SX1262,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc"
    for folder in profiles:
        subprocess.run(
            [a.cli, "compile", "--fqbn", fqbn, str(folder.resolve())], check=True
        )


if __name__ == "__main__":
    main()
