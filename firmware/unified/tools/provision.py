#!/usr/bin/env python3
"""Generate private role sketches offline. Never commit the output directory."""

import argparse
import getpass
import hashlib
import json
from pathlib import Path
import secrets
import shutil

ROOT = Path(__file__).resolve().parents[1]


def bytes_cpp(value):
    return "{" + ",".join(f"0x{x:02x}" for x in value) + "}"


def provision(
    out,
    count=1,
    relays=0,
    fleet=271,
    frequency=915.0,
    power=2,
    password=None,
    servo_mask=0,
):
    if not 1 <= count <= 20 or relays not in (0, 1, 2) or not 1 <= fleet <= 65535:
        raise ValueError("Use 1..20 rovers, 0..2 relays, fleet 1..65535")
    if not 2 <= power <= 17 or not 902 <= frequency <= 928:
        raise ValueError(
            "This package is a 902..928 MHz SX1262 profile; power 2..17 dBm"
        )
    if not 0 <= servo_mask <= 65535 or servo_mask & 0x00F0:
        raise ValueError("Invalid auxiliary mask; M5–M8 are reserved for motors")
    if password is not None and len(password) < 16:
        raise ValueError(
            "Password must have at least 16 characters; random keys are preferred"
        )
    out = Path(out)
    resolved = out.resolve()
    protected = [ROOT.resolve()] + [p for p in ROOT.parents if (p / ".git").exists()]
    if any(resolved.is_relative_to(p) for p in protected):
        raise ValueError("Choose a private output folder outside the source repository/package")
    if out.exists():
        raise ValueError(
            "Destination already exists; refusing to overwrite private keys"
        )
    out.mkdir(parents=True, mode=0o700)
    salt = secrets.token_bytes(16)
    master = (
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
        if password
        else secrets.token_bytes(32)
    )

    def derive(label):
        import hmac

        return hmac.digest(master, label.encode(), "sha256")

    route = derive(f"TeleRC-unified-v1-routing-{fleet}")
    keys = {i: derive(f"TeleRC-unified-v1-rover-{fleet}-{i}") for i in range(1, count + 1)}
    common = f"""#pragma once
#define RELAY_COUNT {relays}
#define FLEET_ID {fleet}
#define FREQUENCY_MHZ {frequency:.3f}f
#define POWER_DBM {power}
#define SERVO_MASK {servo_mask}
#define PROVISIONED 1
struct RoverKey {{ unsigned char id; unsigned char key[32]; }};
static const unsigned char ROUTE_KEY[32]={bytes_cpp(route)};
"""
    profiles = (
        [("BASE", 1, 1, 1)]
        + [(f"ROVER_{i:03}", 2, i, 1) for i in keys]
        + [(f"NODE_{i}", 3, 1, i) for i in range(1, relays + 1)]
    )
    for name, role, rover, node in profiles:
        folder = out / f"TeleRCUnified_{name}"
        folder.mkdir(mode=0o700)
        for p in (ROOT / "firmware").glob("*.h"):
            if p.name != "Config.example.h":
                shutil.copyfile(p, folder / p.name)
        local_keys = keys if role == 1 else {rover: keys[rover]} if role == 2 else {}
        # Relay contains the routing key ONLY, with a dummy empty rover table.
        key_rows = (
            ",".join("{" + f"{i},{bytes_cpp(k)}" + "}" for i, k in local_keys.items())
            or "{0,{0}}"
        )
        config = (
            common
            + f"#define ROLE {role}\n#define ROVER_ID {rover}\n#define NODE_INDEX {node}\nstatic const RoverKey ROVERS[]={{{key_rows}}};\n"
        )
        (folder / "Config.h").write_text(config)
        (folder / f"{folder.name}.ino").write_text(
            '#include <Wire.h>\n#include "Runtime.h"\n'
        )
        for p in folder.iterdir():
            p.chmod(0o600)
    # Salt retained to identify this provisioning event; password is not saved.
    manifest = {
        "version": "0.3.0-rc1",
        "fleet_id": fleet,
        "rovers": list(keys),
        "relays": relays,
        "frequency_mhz": frequency,
        "power_dbm": power,
        "salt_hex": salt.hex(),
        "key_method": "PBKDF2-SHA256/600000 + HMAC subkeys"
        if password
        else "OS random + HMAC subkeys",
        "warning": "Generated sketches contain private keys. Keep offline. No firmware binaries supplied.",
    }
    (out / "PROFILE.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / ".gitignore").write_text("*\n")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--rovers", type=int, default=1)
    p.add_argument("--relays", type=int, choices=[0, 1, 2], default=0)
    p.add_argument("--fleet", type=int, default=271)
    p.add_argument("--frequency", type=float, default=915.0)
    p.add_argument("--power", type=int, default=2)
    p.add_argument(
        "--password", action="store_true", help="Prompt securely; prefer random default"
    )
    p.add_argument("--servo-mask", type=lambda x: int(x, 0), default=0)
    a = p.parse_args()
    secret = None
    if a.password:
        secret = getpass.getpass("Private link passphrase (16+ characters): ")
        if secret != getpass.getpass("Repeat passphrase: "):
            p.error("Passphrases do not match")
    try:
        result = provision(
            a.out,
            a.rovers,
            a.relays,
            a.fleet,
            a.frequency,
            a.power,
            secret,
            a.servo_mask,
        )
    except ValueError as e:
        p.error(str(e))
    print(
        f"Created {len(result['rovers'])} private rover profiles and {a.relays} relays in {a.out}"
    )
    print(
        "All boards must come from this SAME generation. Keep the whole folder private."
    )


if __name__ == "__main__":
    main()
