"""Offline per-rover storage. This module never acquires a radio or authority."""

from pathlib import Path

MAX_MANAGED_ROVERS = 20


def draft_path(root: Path, rover: int) -> Path:
    if type(rover) is not int or not 1 <= rover <= MAX_MANAGED_ROVERS:
        raise ValueError("Rover ID must be an integer from 1 to 20")
    return Path(root) / f"rover-{rover:03d}.json"
