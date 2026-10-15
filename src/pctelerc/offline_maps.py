"""Read-only raster MBTiles; no web server, style CDN or network required."""
from __future__ import annotations

import math
from pathlib import Path
import re
import sqlite3
import time

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageReader


def tile_image(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 2 * 1024 * 1024:
        return QImage()
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if size.width() not in (256, 512) or size.height() != size.width():
        return QImage()
    return reader.read()


class OfflineMap:
    def __init__(self, filename):
        self.path = Path(filename).expanduser().resolve(strict=True)
        self._db = None
        self._deadline = time.monotonic() + .25
        try:
            self._db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=.05)
            self._db.set_progress_handler(lambda: int(time.monotonic() > self._deadline), 1000)
            self._db.execute('PRAGMA query_only=ON')
            self._db.execute('PRAGMA trusted_schema=OFF')
            self.metadata = dict(self._db.execute('SELECT name, value FROM metadata LIMIT 128'))
            fmt = str(self.metadata.get('format', '')).lower()
            if fmt not in {'png', 'jpg', 'jpeg', 'webp', 'image/png', 'image/jpeg', 'image/webp'}:
                raise ValueError('Choose raster MBTiles (PNG, JPEG or WebP). Vector PBF maps need a vector renderer.')
            sample = self._db.execute('SELECT tile_data FROM tiles LIMIT 1').fetchone()
            if not sample or tile_image(sample[0]).isNull():
                raise ValueError('The map has no readable 256 or 512 pixel raster tiles.')
            self._db.execute('SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? LIMIT 1', (0, 0, 0))
            self.xyz = self.metadata.get('scheme', 'tms').lower() == 'xyz'
            self.name = str(self.metadata.get('name', self.path.stem))[:100]
            self.attribution = re.sub('<[^>]+>', '', str(self.metadata.get('attribution', '')))[:300]
            self.center = self._center()
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            self.close()
            if isinstance(exc, ValueError):
                raise
            raise ValueError('Unable to read this MBTiles map. Choose a valid local raster MBTiles file.') from None

    def _center(self):
        try:
            parts = [float(v) for v in self.metadata.get('center', '').split(',')]
            if len(parts) >= 2:
                lon, lat = parts[:2]
                zoom = int(parts[2]) if len(parts) > 2 else 14
            else:
                west, south, east, north = [float(v) for v in self.metadata['bounds'].split(',')]
                lon, lat = (west + east) / 2, (south + north) / 2
                zoom = int(self.metadata.get('minzoom', 14))
            if not all(math.isfinite(v) for v in (lat, lon, zoom)) or not -85.05112878 <= lat <= 85.05112878 or not -180 <= lon <= 180:
                return None
            return lat, lon, max(0, min(22, zoom))
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

    def tile(self, z, x, y):
        self._deadline = time.monotonic() + .025
        try:
            row = y if self.xyz else (1 << z) - 1 - y
            result = self._db.execute('SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? LIMIT 1', (z, x, row)).fetchone()
            return tile_image(result[0]) if result else QImage()
        except sqlite3.Error:
            return QImage()

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None
