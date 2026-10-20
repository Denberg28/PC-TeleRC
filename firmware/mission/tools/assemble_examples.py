#!/usr/bin/env python3
"""Refresh keyless Arduino example folders from the canonical firmware headers."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def assemble():
    template = (ROOT / "firmware/Config.example.h").read_text()
    for name, role, node in [
        ("BASE", 1, 1),
        ("ROVER_001", 2, 1),
        ("NODE_1", 3, 1),
        ("NODE_2", 3, 2),
    ]:
        folder = ROOT / "sketches" / f"TeleRCMission_{name}"
        folder.mkdir(parents=True, exist_ok=True)
        for p in (ROOT / "firmware").glob("*.h"):
            if p.name != "Config.example.h":
                shutil.copyfile(p, folder / p.name)
        config = (
            template.replace("#define ROLE 1", f"#define ROLE {role}")
            .replace("#define NODE_INDEX 1", f"#define NODE_INDEX {node}")
            .replace("#define RELAY_COUNT 0", "#define RELAY_COUNT 2")
        )
        (folder / "Config.h").write_text(config)
        (folder / f"{folder.name}.ino").write_text(
            '// Keyless review example: RF stays OFF. Generate private profiles before use.\n#include <Wire.h>\n#include "Runtime.h"\n'
        )


if __name__ == "__main__":
    assemble()
