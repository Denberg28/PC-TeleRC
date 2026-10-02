from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile


class SingleInstanceGuard:
    """Process-wide guard that prevents two PC TeleRC UI instances."""

    def __init__(self, name: str = "PC-TeleRC"):
        lock_path = Path(tempfile.gettempdir()) / f"{name}.lock"
        self._lock = QLockFile(str(lock_path))
        # Qt records the owner PID/host/app in the lock file and can recover
        # dead-process locks. A short stale threshold avoids persistent crash locks.
        self._lock.setStaleLockTime(30_000)

    def acquire(self, timeout_ms: int = 100) -> bool:
        return bool(self._lock.tryLock(timeout_ms))

    def release(self) -> None:
        if self._lock.isLocked():
            self._lock.unlock()
