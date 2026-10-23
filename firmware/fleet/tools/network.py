#!/usr/bin/env python3
"""Create one private fleet, then add boards without changing existing firmware."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0-dev1"


def validate(network):
    if network.get("format") != "TeleRC-TF2-1":
        raise ValueError("Not a TF2 fleet credentials file")
    if not 1 <= network["fleet_id"] <= 65535:
        raise ValueError("Fleet ID must be 1..65535")
    if not 850 <= network["frequency"] <= 930 or not 2 <= network["power"] <= 17:
        raise ValueError("Invalid radio configuration")
    if network["servo_mask"] & ~0x700:
        raise ValueError("Only dedicated outputs 9/10/11 can be opted in")
    for key in ("route_key", "endpoint_root"):
        if len(bytes.fromhex(network[key])) != 32 or not any(bytes.fromhex(network[key])):
            raise ValueError("Invalid private key")


def config(network, role):
    validate(network)
    def key(name, value):
        return f'static const uint8_t {name}[32]={{' + ','.join(f'0x{v:02x}' for v in bytes.fromhex(value)) + '};\n'
    result = ('#pragma once\n#include <stdint.h>\n// PRIVATE: reuse this configuration; never publish it.\n'
              f'#define PROVISIONED 1\n#define FLEET_ID {network["fleet_id"]}\n'
              f'#define FREQUENCY_MHZ {network["frequency"]:.3f}f\n#define POWER_DBM {network["power"]}\n'
              f'#define SERVO_MASK {network["servo_mask"]}\n')
    result += key('ROUTE_KEY', network['route_key'])
    if role != 'node':
        result += key('ENDPOINT_ROOT', network['endpoint_root'])
    return result


def sketch(out, role, identity=1, network=None):
    limits = {'base': 1, 'rover': 20, 'node': 200}
    if role not in limits or not 1 <= identity <= limits[role]:
        raise ValueError('Invalid role or ID')
    out = Path(out)
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite {out}')
    out.mkdir(parents=True, mode=0o700)
    symbol = 'ROVER_ID' if role == 'rover' else 'NODE_ID'
    text = '// TeleRC Fleet 1.1.0-dev1 / TF2. Keep IDs unique within this fleet.\n'
    text += f'#define ROLE {dict(base=1, rover=2, node=3)[role]}\n'
    if role != 'base':
        text += f'#define {symbol} {identity}  // EDIT ONLY THIS NUMBER before uploading a new {role}.\n'
    text += '#include "Runtime.h"\n'
    (out / (out.name + '.ino')).write_text(text)
    for file in (ROOT / 'firmware').glob('*.h'):
        if file.name != 'NetworkConfig.example.h':
            shutil.copyfile(file, out / file.name)
    content = config(network, role) if network else (ROOT/'firmware/NetworkConfig.example.h').read_text()
    target = out / 'NetworkConfig.h'
    target.write_text(content)
    if network:
        target.chmod(0o600)
    return out


def init(out, fleet_id=271, frequency=915.0, power=2, servo_mask=0):
    out = Path(out)
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite {out}')
    network = dict(format='TeleRC-TF2-1', fleet_id=fleet_id, frequency=frequency,
                   power=power, servo_mask=servo_mask, route_key=secrets.token_hex(32),
                   endpoint_root=secrets.token_hex(32))
    validate(network)
    out.mkdir(parents=True, mode=0o700)
    credentials = out / 'FleetCredentials.json'
    credentials.write_text(json.dumps(network, indent=2)+'\n')
    credentials.chmod(0o600)
    for role, identity in [('base',1),('rover',1),('node',1),('node',2)]:
        name = f'TeleRCFleet_{role.upper()}' + (f'_{identity:03d}' if role != 'base' else '')
        sketch(out/name, role, identity, network)
    return credentials


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    first = sub.add_parser('init', help='Run once per private fleet')
    first.add_argument('--out', type=Path, required=True)
    first.add_argument('--fleet-id', type=int, default=271)
    first.add_argument('--frequency', type=float, default=915)
    first.add_argument('--power', type=int, default=2)
    first.add_argument('--servo-mask', type=lambda x:int(x,0), default=0)
    add = sub.add_parser('add', help='Reuse fleet keys; no old board rebuild')
    add.add_argument('--network', type=Path, required=True)
    add.add_argument('--role', choices=('base','rover','node'), required=True)
    add.add_argument('--id', type=int, default=1)
    add.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.action == 'init':
            result = init(args.out,args.fleet_id,args.frequency,args.power,args.servo_mask)
            print(f'Created private fleet: {result}. Back it up privately; do not regenerate for each board.')
        else:
            network = json.loads(args.network.read_text())
            result = sketch(args.out,args.role,args.id,network)
            print(f'Created {result}. Existing boards do not change.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        p.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
