"""Generate a matching private fleet without shell interpolation or shared default keys."""

from pathlib import Path
from provision import provision


def main():
    print("TeleRC Mission 0.2.0 · matching BASE / ROVER / NODE sketches")
    rovers = int(input("Number of rovers [1..20]: ").strip() or "1")
    relays = int(input("Relay nodes on each fixed route [0..2]: ").strip() or "0")
    out = Path(input("New private output folder: ").strip()).expanduser()
    if not str(out) or out == Path("."):
        raise ValueError("Choose a new private folder")
    result = provision(out, count=rovers, relays=relays)
    print(f"Created {len(result['rovers'])} rover profiles; {relays} relay(s).")
    print(
        "Flash every participating board from this same set. Keep generated Config.h files private."
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
