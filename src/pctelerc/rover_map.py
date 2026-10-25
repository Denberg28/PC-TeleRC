"""Small read-only GPS map with bounded asynchronous tile fetching."""
from __future__ import annotations

from collections import OrderedDict, deque
import json
import math
from pathlib import Path
import time

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget

from . import __version__
from .config import data_dir
from .core import LinkState
from .offline_maps import OfflineMap, tile_image


def world_pixel(latitude, longitude, zoom):
    latitude = max(-85.05112878, min(85.05112878, latitude))
    size = 256 * (2 ** zoom)
    x = (longitude + 180) / 360 * size
    y = (1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * size
    return x, y


def world_location(x, y, zoom):
    """Inverse of world_pixel, including dateline wrapping and Mercator bounds."""
    size = 256 * (2 ** zoom)
    x, y = x % size, max(0, min(size, y))
    return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2*y/size)))),
            x/size*360 - 180)


def position_fresh(snapshot, now=None):
    now = time.monotonic() if now is None else now
    return (snapshot.state == LinkState.CONNECTED and snapshot.gps_fix >= 3
            and snapshot.latitude is not None and snapshot.longitude is not None
            and snapshot.position_timestamp is not None
            and 0 <= now - snapshot.position_timestamp <= 5)


class RoverMap(QWidget):
    TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    CACHE_SECONDS = 7 * 24 * 3600
    DRAG_THRESHOLD = 5
    # Same display-only starting view as TeleRC; never a measured rover fix.
    DEFAULT_CENTER = (13.6218, 123.1948)

    def __init__(self, parent=None, *, cache_dir: Path | None = None):
        super().__init__(parent)
        # Paint every pixel through one Qt backing-store pass. In particular,
        # Windows must not erase a styled QWidget background between resize
        # frames before the terrain and mission/fleet overlays are painted.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMinimumSize(220, 150)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._zoom = 17
        self._snapshot = None
        self._center = self.DEFAULT_CENTER
        self._home = None
        self._track = deque(maxlen=500)
        self._tiles = OrderedDict()
        self._pending = {}
        self._failed = {}
        self._online = True
        self._offline_map = None
        self._offline_missing = set()
        self._generation = 0
        self._last_position = None
        self._drag = None
        self._drag_origin = None
        self._drag_world = None
        self._dragging = False
        self._last_dragged = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self._follow = True
        self._cache_dir = cache_dir or data_dir() / "map-cache"
        self._view_path = self._cache_dir.parent / "map-view.json"
        self._load_view()
        self._manager = QNetworkAccessManager(self)
        self._last_timestamp = None
        self._closed = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(1000)

    def _load_view(self):
        try:
            view = json.loads(self._view_path.read_text())
            lat, lon, zoom = float(view['latitude']), float(view['longitude']), int(view['zoom'])
            if math.isfinite(lat) and math.isfinite(lon) and -85.05112878 <= lat <= 85.05112878 and -180 <= lon <= 180:
                self._center = (lat, lon)
                self._zoom = max(0, min(22, zoom))
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def set_offline_map(self, filename):
        # Validate the replacement before releasing the current map.
        candidate = OfflineMap(filename) if filename else None
        if self._offline_map is not None:
            self._offline_map.close()
        self._offline_map = candidate
        self._generation += 1
        for reply in list(self._pending.values()):
            reply.abort()
        self._tiles.clear(); self._offline_missing.clear(); self._failed.clear()
        if candidate is not None and candidate.center is not None and self._last_position is None:
            lat, lon, self._zoom = candidate.center
            self._center = (lat, lon)
        self.update()

    def locate_rover(self):
        self.cancel_pan()
        self._follow = True
        if self._last_position is not None:
            self._center = self._last_position
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._center is not None:
            self._drag = QPointF(event.position())
            self._drag_origin = QPointF(event.position())
            self._drag_world = world_pixel(*self._center, self._zoom)
            self._dragging = False
            self._last_dragged = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def _manual_view(self):
        self._follow = False

    def _pan_to(self, point):
        if self._drag_origin is None or self._drag_world is None:
            return
        delta = point - self._drag_origin
        if not self._dragging:
            if delta.manhattanLength() < self.DRAG_THRESHOLD:
                return
            self._dragging = True
            self._drag_world = world_pixel(*self._center, self._zoom)
            self._manual_view()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._drag = QPointF(point)
        x, y = self._drag_world
        center = world_location(x-delta.x(), y-delta.y(), self._zoom)
        if center != self._center:
            self._center = center
            self.update()

    def cancel_pan(self):
        self._drag = self._drag_origin = self._drag_world = None
        self._dragging = False
        self._last_dragged = True
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._pan_to(event.position())
            else:
                self.cancel_pan()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag is not None:
            self._pan_to(event.position())
            dragged = self._dragging
            self.cancel_pan()
            self._last_dragged = dragged
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def event(self, event):
        if event.type() in (QEvent.Type.UngrabMouse,QEvent.Type.WindowDeactivate,QEvent.Type.Hide):
            if getattr(self, '_drag', None) is not None:
                self.cancel_pan()
        return super().event(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self.zoom(1 if delta > 0 else -1)
            event.accept()
        else:
            event.ignore()

    def set_online(self, online):
        self._online = online
        if not online:
            for reply in list(self._pending.values()):
                reply.abort()
        self.update()

    def set_snapshot(self, snapshot):
        previous = self._snapshot
        self._snapshot = snapshot
        if previous is not None and previous.vehicle_system != snapshot.vehicle_system:
            self._track.clear(); self._home = None
            self._last_timestamp = None; self._last_position = None
        if position_fresh(snapshot) and snapshot.position_timestamp != self._last_timestamp:
            point = (snapshot.latitude, snapshot.longitude)
            self._last_position = point
            if self._follow:
                self._center = point
            if self._home is None:
                self._home = point
            if not self._track or self._track[-1] != point:
                self._track.append(point)
            self._last_timestamp = snapshot.position_timestamp
        self.update()

    def zoom(self, step):
        self.cancel_pan()
        self._manual_view()
        self._zoom = max(0, min(22 if self._offline_map else 19, self._zoom + step))
        self.update()

    def shutdown(self):
        self.cancel_pan()
        self._closed = True
        if self._center is not None:
            try:
                self._view_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self._view_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(dict(latitude=self._center[0], longitude=self._center[1], zoom=self._zoom)))
                temporary.replace(self._view_path)
            except OSError:
                pass
        if self._offline_map is not None:
            self._offline_map.close()
            self._offline_map = None
        self._timer.stop()
        for reply in list(self._pending.values()):
            reply.abort()

    def _tile(self, key):
        if key in self._tiles:
            self._tiles.move_to_end(key)
            return self._tiles[key]
        if self._offline_map is not None:
            if key not in self._offline_missing:
                image = self._offline_map.tile(*key)
                if not image.isNull():
                    image = image.scaled(256, 256)
                    self._remember(key, image)
                    return image
                self._offline_missing.add(key)
                if len(self._offline_missing) > 256:
                    self._offline_missing.clear()
            return None
        path = self._cache_dir / ("-".join(map(str, key)) + ".png")
        try:
            if path.exists():
                image = QImage(str(path))
                if image.width() == 256 and image.height() == 256:
                    self._remember(key, image)
                    # Keep old coverage visible while attempting conditional refresh.
                    if (self._online and not self._closed and time.time() - path.stat().st_mtime >= self.CACHE_SECONDS
                            and key not in self._pending and len(self._pending) < 4):
                        self._request_tile(key, path)
                    return image
        except OSError:
            pass
        if (self._online and not self._closed and key not in self._pending
                and len(self._pending) < 4 and time.monotonic() >= self._failed.get(key, 0)):
            self._request_tile(key, path)
        return None

    def _remember(self, key, image):
        self._tiles[key] = image
        # A large/high-DPI viewport can show more than 64 tiles. Evicting a
        # still-visible tile on every frame causes loading flashes on resize.
        visible = (math.ceil(self.width()/256)+2)*(math.ceil(self.height()/256)+2)
        budget = max(64, min(256, visible*2))
        while len(self._tiles) > budget:
            self._tiles.popitem(last=False)

    def _fallback_tile(self, key):
        """Keep cached lower-detail coverage visible while new tiles arrive."""
        z, x, y = key
        for levels in range(1, min(4, z) + 1):
            scale = 2 ** levels
            parent = (z - levels, x // scale, y // scale)
            image = self._tiles.get(parent)
            if image is None:
                path = self._cache_dir / ("-".join(map(str, parent)) + ".png")
                image = QImage(str(path)) if path.exists() else QImage()
                if image.width() != 256 or image.height() != 256:
                    continue
                self._remember(parent, image)
            side = 256 // scale
            return image.copy((x % scale) * side, (y % scale) * side, side, side).scaled(
                256, 256, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return None

    def _request_tile(self, key, path):
        z, x, y = key
        generation = self._generation
        request = QNetworkRequest(QUrl(self.TILE_URL.format(z=z, x=x, y=y)))
        # First HTTPS setup can be slower than subsequent tiles. This affects
        # display loading only; radio and input watchdogs are independent.
        request.setTransferTimeout(15000)
        request.setRawHeader(b"User-Agent", f"PC-TeleRC/{__version__} (+https://github.com/Denberg28/PC-TeleRC)".encode())
        metadata_path = path.with_suffix(".json")
        try:
            metadata = json.loads(metadata_path.read_text())
            for header in ("ETag", "Last-Modified"):
                if metadata.get(header):
                    conditional = "If-None-Match" if header == "ETag" else "If-Modified-Since"
                    request.setRawHeader(conditional.encode(), metadata[header].encode())
        except (OSError, ValueError):
            pass
        reply = self._manager.get(request)
        reply.setReadBufferSize(256 * 1024)
        self._pending[key] = reply
        buffer = bytearray()
        def consume():
            buffer.extend(bytes(reply.readAll()))
            if len(buffer) > 256 * 1024:
                reply.abort()
        reply.readyRead.connect(consume)
        def complete():
            if self._pending.get(key) is reply:
                self._pending.pop(key, None)
            if self._closed or generation != self._generation:
                reply.deleteLater(); return
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:
                if status == 304 and path.exists():
                    path.touch()
                    image = QImage(str(path))
                else:
                    image = tile_image(bytes(buffer)) if reply.error() == QNetworkReply.NetworkError.NoError else QImage()
                if image.width() == 256 and image.height() == 256:
                    self._remember(key, image)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(str(path))
                    metadata_path.write_text(json.dumps({h:bytes(reply.rawHeader(h)).decode("latin1") for h in ("ETag", "Last-Modified")}))
                else:
                    transient = reply.error() in (QNetworkReply.NetworkError.TimeoutError,
                        QNetworkReply.NetworkError.TemporaryNetworkFailureError,
                        QNetworkReply.NetworkError.RemoteHostClosedError)
                    self._failed[key] = time.monotonic() + (2 if transient else 30)
            except OSError:
                pass
            reply.deleteLater()
            self.update()
        reply.finished.connect(complete)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.save()
        self._paint_map(painter)
        painter.restore()
        self._paint_overlays(painter)

    def _paint_overlays(self, painter):
        """Subclass overlays share the same painter and backing-store frame."""

    def _paint_map(self, painter):
        painter.fillRect(self.rect(), QColor("#182330"))
        if self._center is None:
            painter.setPen(QColor("#c2cedd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "MAP\nWaiting for rover GPS")
            return
        cx, cy = world_pixel(*self._center, self._zoom)
        left, top = cx - self.width()/2, cy - self.height()/2
        total = 2 ** self._zoom
        visible_tiles = 0
        coverage = [(x, y)
                    for x in range(math.floor(left/256), math.floor((left+self.width())/256)+1)
                    for y in range(math.floor(top/256), math.floor((top+self.height())/256)+1)
                    if 0 <= y < total]
        # Load the center first so the operator sees useful coverage immediately.
        coverage.sort(key=lambda tile: (tile[0]*256+128-cx)**2 + (tile[1]*256+128-cy)**2)
        for x, y in coverage:
            key = (self._zoom, x % total, y)
            tile = self._tile(key)
            if tile is None and self._offline_map is None:
                tile = self._fallback_tile(key)
            if tile is not None:
                visible_tiles += 1
                painter.drawImage(QPointF(x*256-left, y*256-top), tile)
        def project(point):
            x, y = world_pixel(*point, self._zoom)
            dx = (x-cx + total*128) % (total*256) - total*128
            return QPointF(self.width()/2+dx, y-top)
        if self._track:
            path = QPainterPath(project(self._track[0]))
            for point in self._track:
                path.lineTo(project(point))
            painter.setPen(QPen(QColor("#0ea5e9"), 3))
            painter.drawPath(path)
        if self._home is not None:
            home = project(self._home)
            painter.setBrush(QColor("#fbbf24")); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(home, 5, 5)
        fresh = self._snapshot is not None and position_fresh(self._snapshot)
        if self._last_position is not None:
            painter.save()
            painter.translate(project(self._last_position))
            heading = self._snapshot.heading if self._snapshot is not None else None
            painter.rotate(heading or 0)
            rover = QPainterPath(); rover.moveTo(0,-13); rover.lineTo(9,10); rover.lineTo(0,6); rover.lineTo(-9,10); rover.closeSubpath()
            painter.setBrush(QColor("#38bdf8" if fresh else "#9ca3af")); painter.setPen(QPen(QColor("#ffffff"),1))
            if heading is None:
                painter.drawEllipse(QPointF(0,0),7,7)
            else:
                painter.drawPath(rover)
            painter.restore()
        status = "GPS live" if fresh else "GPS stale" if self._last_position else "Waiting for GPS"
        if self._offline_map or not self._online:
            status += " · offline"
        # Shadowed text, leaving the map visible behind its status.
        painter.setPen(QColor("#10151c")); painter.drawText(9,17,status)
        painter.setPen(QColor("#ffffff")); painter.drawText(8,16,status)
        if not visible_tiles:
            message = ("Loading map…" if self._pending else "Map unavailable · retrying") if self._online and not self._offline_map else "No offline coverage"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)
        painter.fillRect(QRectF(0,self.height()-20,self.width(),20),QColor(10,16,24,220))
        font=painter.font(); font.setPointSize(8); painter.setFont(font)
        painter.setPen(QColor("#e2e8f0")); painter.drawText(6,self.height()-6, painter.fontMetrics().elidedText(
            (self._offline_map.attribution or self._offline_map.name) if self._offline_map else "© OpenStreetMap contributors",
            Qt.TextElideMode.ElideRight, self.width()-12))

