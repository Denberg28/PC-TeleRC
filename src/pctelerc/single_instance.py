from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile


class SingleInstanceGuard:
    """Process-wide guard that prevents two PC TeleRC UI instances."""

    def __init__(self, name: str = "PC-TeleRC"):
        lock_path = Path(tempfile.gettempdir()) / f"{name}.lock"
        self._lock = QLockFile(str(lock_path))
        # This lock protects a whole application session. Never expire it by
        # age; Qt still detects a dead owning process using PID/host/app metadata.
        self._lock.setStaleLockTime(0)

    def acquire(self, timeout_ms: int = 100) -> bool:
        return bool(self._lock.tryLock(timeout_ms))

    def release(self) -> None:
        if self._lock.isLocked():
            self._lock.unlock()
