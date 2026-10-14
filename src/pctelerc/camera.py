"""Display-only camera transport. No control, arm, link or input side effects."""
from __future__ import annotations

import time
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QMediaPlayer, QVideoSink
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget


def validate_camera_url(value: str, *, mjpeg=False) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    allowed = {"http", "https"} if mjpeg else {"http", "https", "rtsp", "rtsps"}
    if parsed.scheme.lower() not in allowed or not parsed.hostname or any(c.isspace() for c in value):
        raise ValueError("Enter a valid HTTP(S) or RTSP camera URL.")
    # Validate malformed ports before a backend gets the string.
    _ = parsed.port
    return value


def stored_camera_url(value: str) -> str:
    """Do not persist embedded passwords, query tokens or URL fragments."""
    if not value.strip():
        return ""
    parsed = urlsplit(validate_camera_url(value))
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


class MjpegBuffer:
    MAX_BYTES = 2 * 1024 * 1024

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> bytes | None:
        self.buffer.extend(data)
        latest = None
        while True:
            start = self.buffer.find(b"\xff\xd8")
            if start < 0:
                self.buffer[:] = self.buffer[-1:]
                break
            if start:
                del self.buffer[:start]
            end = self.buffer.find(b"\xff\xd9", 2)
            if end < 0:
                if len(self.buffer) > self.MAX_BYTES:
                    self.buffer.clear()
                break
            if end + 2 <= self.MAX_BYTES:
                latest = bytes(self.buffer[:end + 2])
            del self.buffer[:end + 2]
        return latest


class CameraView(QWidget):
    statusChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CameraView")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(480, 270)
        self._image = QImage()
        self._generation = 0
        self._active = False
        self._last_frame = None
        self._last_convert = 0.
        self._started = 0.
        self._status = "Camera off"
        self._player = None
        self._camera = None
        self._capture = None
        self._sink = None
        self._reply = None
        self._network = QNetworkAccessManager(self)
        self._mjpeg = MjpegBuffer()
        self._watchdog = QTimer(self)
        self._watchdog.timeout.connect(self._check_age)
        self._watchdog.start(250)

    @staticmethod
    def devices():
        return [(bytes(d.id().toHex()).decode("ascii"), d.description()) for d in QMediaDevices.videoInputs()]

    def start(self, mode: str, *, device_id="", url=""):
        self.stop()
        token = self._generation
        try:
            if mode == "usb":
                devices = QMediaDevices.videoInputs()
                chosen = next((d for d in devices if bytes(d.id().toHex()).decode("ascii") == device_id), None)
                if chosen is None:
                    raise ValueError("Select an available USB camera.")
            else:
                url = validate_camera_url(url, mjpeg=mode == "mjpeg")
            self._active = True
            self._started = time.monotonic()
            self._set_status("Connecting camera…")
            if mode == "mjpeg":
                self._mjpeg = MjpegBuffer()
                request = QNetworkRequest(QUrl(url))
                request.setTransferTimeout(8000)
                request.setRawHeader(b"User-Agent", b"PC-TeleRC camera")
                self._reply = self._network.get(request)
                reply = self._reply
                reply.setReadBufferSize(MjpegBuffer.MAX_BYTES)
                reply.readyRead.connect(lambda: self._read_mjpeg(reply, token))
                reply.finished.connect(lambda: self._mjpeg_finished(reply, token))
            else:
                self._sink = QVideoSink(self)
                self._sink.videoFrameChanged.connect(lambda frame: self._video_frame(frame, token))
                if mode == "usb":
                    self._capture = QMediaCaptureSession(self)
                    self._camera = QCamera(chosen, self)
                    formats = [f for f in chosen.videoFormats() if f.resolution().width() <= 1280 and f.maxFrameRate() <= 30]
                    if formats:
                        self._camera.setCameraFormat(max(formats, key=lambda f: f.resolution().width() * f.resolution().height()))
                    self._camera.errorOccurred.connect(lambda *_: self._error(token))
                    self._capture.setCamera(self._camera)
                    self._capture.setVideoSink(self._sink)
                    self._camera.start()
                elif mode == "network":
                    self._player = QMediaPlayer(self)
                    self._player.setVideoSink(self._sink)
                    self._player.errorOccurred.connect(lambda *_: self._error(token))
                    self._player.setSource(QUrl(url))
                    self._player.play()
                else:
                    raise ValueError("Select USB, network video or HTTP MJPEG.")
            return True
        except (ValueError, RuntimeError):
            self.stop()
            self._set_status("Camera unavailable — check source, URL or device")
            return False

    def stop(self):
        self._generation += 1
        self._active = False
        if self._reply is not None:
            self._reply.abort()
            self._reply.deleteLater()
            self._reply = None
        if self._player is not None:
            self._player.stop()
            self._player.deleteLater()
            self._player = None
        if self._camera is not None:
            self._camera.stop()
            self._camera.deleteLater()
            self._camera = None
        for name in ("_capture", "_sink"):
            obj = getattr(self, name)
            if obj is not None:
                obj.deleteLater()
                setattr(self, name, None)
        self._last_frame = None
        self._last_convert = 0.
        self._image = QImage()
        self._set_status("Camera off")
        self.update()

    def shutdown(self):
        self._watchdog.stop()
        self.stop()

    def _video_frame(self, frame, token):
        if not self._active or token != self._generation or not frame.isValid():
            return
        now = time.monotonic()
        if now - self._last_convert < 1 / 20:
            return
        self._last_convert = now
        self._accept_image(frame.toImage(), token)

    def _read_mjpeg(self, reply, token):
        if not self._active or token != self._generation:
            return
        data = self._mjpeg.feed(bytes(reply.readAll()))
        if data is not None:
            now = time.monotonic()
            if now - self._last_convert >= 1 / 20:
                self._last_convert = now
                buffer=QBuffer(); buffer.setData(QByteArray(data)); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                reader=QImageReader(buffer,b"JPEG")
                size=reader.size()
                if 0 < size.width() <= 4096 and 0 < size.height() <= 4096 and size.width()*size.height() <= 8_000_000:
                    self._accept_image(reader.read(), token)

    def _accept_image(self, image, token):
        if not self._active or token != self._generation or image.isNull():
            return
        if image.width() > 4096 or image.height() > 4096:
            self._error(token)
            return
        self._image = image
        self._last_frame = time.monotonic()
        self._set_status("Live camera")
        self.update()

    def _mjpeg_finished(self, reply, token):
        if self._active and token == self._generation:
            self._error(token)

    def _error(self, token):
        if token != self._generation:
            return
        self.stop()
        # Backend error strings can contain embedded camera credentials.
        self._set_status("Camera unavailable — check network, device and video format")

    def _check_age(self):
        if not self._active:
            return
        age = time.monotonic() - (self._last_frame if self._last_frame is not None else self._started)
        if age > 1.5:
            self._set_status("Video stale — waiting for frames" if self._last_frame is not None else "Waiting for camera frames…")
            self.update()

    def _set_status(self, text):
        if text != self._status:
            self._status = text
            self.statusChanged.emit(text)

    def mousePressEvent(self, event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#090d12"))
        if not self._image.isNull():
            size = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x, y = (self.width() - size.width()) // 2, (self.height() - size.height()) // 2
            painter.drawImage(x, y, self._image.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
        else:
            painter.setPen(QColor("#5a6a7f"))
            for fraction in (1/3, 2/3):
                painter.drawLine(int(self.width()*fraction), 0, int(self.width()*fraction), self.height())
                painter.drawLine(0, int(self.height()*fraction), self.width(), int(self.height()*fraction))
        stale = self._last_frame is not None and time.monotonic() - self._last_frame > 1.5
        if self._image.isNull() or stale:
            if stale:
                painter.fillRect(self.rect(), QColor(9, 13, 18, 175))
            painter.setPen(QColor("#c9d3df"))
            font = painter.font(); font.setPointSize(14); painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             self._status + ("\nChoose a camera source in Settings" if self._image.isNull() else ""))
        painter.setPen(QPen(QColor("#38bdf8" if self.hasFocus() else "#293544"), 2 if self.hasFocus() else 1))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
