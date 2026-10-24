"""Map route editor and explicit LoRa mission commissioning UI."""

from pathlib import Path
import json
import math
import queue
import time

from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QListWidget,
    QPlainTextEdit,
    QFileDialog,
    QLineEdit,
    QDialogButtonBox,
    QSplitter,
    QScrollArea,
    QFrame,
)

from .mission_plan import Plan, Point, Function, parse_text
from .mission_protocol.client import fingerprint
from .mission_service import MissionService
from .rover_map import RoverMap, world_pixel
from .lora_setup_widget import refresh_ports
from .config import data_dir
from .fleet import draft_path as fleet_draft_path


class MissionMap(RoverMap):
    location = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.press = None
        self.moved = False
        self.setMinimumSize(350, 250)

    def mousePressEvent(self, event):
        self.press = (
            event.position() if event.button() == Qt.MouseButton.LeftButton else None
        )
        self.moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self.press is not None
            and (event.position() - self.press).manhattanLength() > 5
        ):
            self.moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.press is not None and not self.moved and self._center is not None:
            x, y = world_pixel(*self._center, self._zoom)
            size = 256 * 2**self._zoom
            x += event.position().x() - self.width() / 2
            y = max(0, min(size, y + event.position().y() - self.height() / 2))
            lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / size))))
            lon = (x / size * 360 + 180) % 360 - 180
            self.location.emit(lat, lon)
        self.press = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._center is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = world_pixel(*self._center, self._zoom)
        size = 256 * 2**self._zoom
        previous = None
        for i, point in enumerate(self.points):
            x, y = world_pixel(*point, self._zoom)
            p = QPointF(
                self.width() / 2 + (x - cx + size / 2) % size - size / 2,
                self.height() / 2 + y - cy,
            )
            painter.setPen(QPen(QColor("#fbbf24"), 2))
            if previous is not None:
                painter.drawLine(previous, p)
            painter.setBrush(QColor("#142438"))
            painter.drawEllipse(p, 12, 12)
            painter.setPen(QColor("white"))
            painter.drawText(int(p.x() - 8), int(p.y() + 5), str(i + 1))
            previous = p


class MissionDialog(QDialog):
    def __init__(self, prepare_link, parent=None, service=None, draft_path=None):
        super().__init__(parent)
        self.prepare_link = prepare_link
        self.service = service or MissionService()
        self.plan = Plan()
        self.imported = None
        self.digest = ""
        self.busy = False
        self.connected = False
        self._plan_valid = False
        self._phase_text = "Planning"
        self._last_snapshot = None
        self._fleet_root = None if draft_path is not None else data_dir() / "fleet-plans"
        self._draft_path = (
            Path(draft_path)
            if draft_path is not None
            else fleet_draft_path(self._fleet_root, 1)
        )
        # Retain the previous single-rover draft only for rover 1. Never apply
        # that draft implicitly to a newly selected vehicle.
        if self._fleet_root is not None and not self._draft_path.exists():
            legacy = data_dir() / "mission-draft.json"
            if legacy.is_file() and legacy.stat().st_size <= 120000:
                self._draft_path.parent.mkdir(parents=True, exist_ok=True)
                self._draft_path.write_bytes(legacy.read_bytes())
        self.setWindowTitle("Fleet missions · PC TeleRC")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.resize(1100, 760)
        self.setMinimumSize(850, 600)
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Plan  →  Connect  →  Upload  →  Start"), 1)
        self.plan_toggle = QPushButton("Hide plan")
        self.plan_toggle.setCheckable(True)
        self.plan_toggle.setChecked(True)
        self.help_toggle = QPushButton("Help")
        self.help_toggle.setCheckable(True)
        toolbar.addWidget(self.plan_toggle)
        toolbar.addWidget(self.help_toggle)
        root.addLayout(toolbar)
        link = QHBoxLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.setPlaceholderText("BASE COM port")
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.setToolTip("Refresh USB ports")
        self.refresh_btn.clicked.connect(lambda: refresh_ports(self.port))
        self.rover = QSpinBox()
        self.rover.setRange(1, 20)
        self.rover.setToolTip("Match the rover sketch ID and FC SYSID_THISMAV; one active rover at a time")
        self.rover.setFixedWidth(70)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect)
        self.close_btn = QPushButton("Disconnect")
        self.close_btn.clicked.connect(self._disconnect)
        for w in (
            QLabel("BASE"),
            self.port,
            self.refresh_btn,
            QLabel("Rover"),
            self.rover,
            self.connect_btn,
            self.close_btn,
        ):
            link.addWidget(w)
        root.addLayout(link)
        self.status = QLabel("Planning · offline")
        self.status.setWordWrap(True)
        self.telemetry = QLabel("No FC telemetry")
        self.telemetry.setObjectName("Muted")
        self.firmware_label = QLabel("BASE firmware: not connected")
        self.firmware_label.setObjectName("Muted")
        self.firmware_label.setWordWrap(True)
        root.addWidget(self.firmware_label)
        root.addWidget(self.status)
        root.addWidget(self.telemetry)
        body = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(body, 1)
        self.map = MissionMap()
        body.addWidget(self.map)
        editor = QWidget()
        el = QVBoxLayout(editor)
        el.setContentsMargins(0, 0, 0, 0)
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.editor_scroll.setMinimumWidth(350)
        self.editor_scroll.setWidget(editor)
        body.addWidget(self.editor_scroll)
        editor.setMinimumHeight(410)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 1)
        self.plan_toggle.toggled.connect(self.editor_scroll.setVisible)
        self.plan_toggle.toggled.connect(
            lambda shown: self.plan_toggle.setText(
                "Hide plan" if shown else "Show plan"
            )
        )
        self.editor = editor
        self.editor.setMinimumWidth(330)
        body.setSizes([700, 360])
        self._editing_controls = []
        self.mode = QComboBox()
        self.mode.addItem("Waypoint", None)
        for i in range(3):
            for on in (True, False):
                self.mode.addItem(f"F{i + 1} " + ("ON" if on else "OFF"), (i, on))
        self.mode.setToolTip(
            "Choose an F event, then tap its location. Waypoint mode resumes after each tap."
        )
        el.addWidget(self.mode)
        coords = QFormLayout()
        self.lat = QDoubleSpinBox()
        self.lat.setRange(-85, 85)
        self.lat.setDecimals(7)
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180, 180)
        self.lon.setDecimals(7)
        coords.addRow("Latitude", self.lat)
        coords.addRow("Longitude", self.lon)
        el.addLayout(coords)
        row = QHBoxLayout()
        add = QPushButton("Add location")
        add.clicked.connect(lambda: self._add(self.lat.value(), self.lon.value()))
        center = QPushButton("Center map")
        center.clicked.connect(self._center)
        row.addWidget(add)
        row.addWidget(center)
        el.addLayout(row)
        self.rows = QListWidget()
        self.rows.setMinimumHeight(90)
        el.addWidget(self.rows, 1)
        row = QHBoxLayout()
        for label, callback in [
            ("↑", lambda: self._move(-1)),
            ("↓", lambda: self._move(1)),
            ("Remove", self._remove),
            ("Clear", self._clear),
        ]:
            b = QPushButton(label)
            b.clicked.connect(callback)
            row.addWidget(b)
            self._editing_controls.append(b)
        el.addLayout(row)
        self.advanced_toggle = QPushButton("Output settings")
        self.advanced_toggle.setCheckable(True)
        el.addWidget(self.advanced_toggle)
        self.output_settings = QWidget()
        output_layout = QVBoxLayout(self.output_settings)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_settings.hide()
        self.advanced_toggle.toggled.connect(self.output_settings.setVisible)
        self.advanced_toggle.toggled.connect(
            lambda expanded: self.editor.setMinimumHeight(550 if expanded else 410)
        )
        output_layout.addWidget(QLabel("Function · Output · OFF / ON (µs)"))
        self.functions = []
        for i in range(3):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"F{i + 1}"))
            ch = QSpinBox()
            ch.setRange(0, 16)
            ch.setSpecialValueText("Unset")
            ch.setToolTip(f"F{i + 1} dedicated output")
            off = QSpinBox()
            off.setToolTip("OFF PWM")
            off.setRange(1000, 2000)
            off.setValue(1100)
            on = QSpinBox()
            on.setToolTip("ON PWM")
            on.setRange(1000, 2000)
            on.setValue(1900)
            for w in (ch, off, on):
                row.addWidget(w)
                w.valueChanged.connect(self._invalidate)
            output_layout.addLayout(row)
            self.functions.append((ch, off, on))
        el.addWidget(self.output_settings)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.1, 3)
        self.speed.setSingleStep(0.1)
        self.speed.setValue(0.5)
        self.speed.setSuffix(" m/s")
        self.speed.valueChanged.connect(self._invalidate)
        el.addWidget(self.speed)
        row = QHBoxLayout()
        load = QPushButton("Import WPL")
        save = QPushButton("Export WPL")
        load.clicked.connect(self._import)
        save.clicked.connect(self._export)
        row.addWidget(load)
        row.addWidget(save)
        el.addLayout(row)
        self._editing_controls += [self.mode, self.lat, self.lon, add, load, self.speed]
        self._editing_controls += [w for row in self.functions for w in row]
        for widget in [
            self.lat,
            self.lon,
            self.speed,
            *[w for row in self.functions for w in row],
        ]:
            widget.setMinimumHeight(28)
        policy = QHBoxLayout()
        self.continue_loss = QCheckBox("Continue AUTO on link loss")
        self.continue_loss.setToolTip(
            "Requires the FC continuation profile. Default is HOLD on GCS loss."
        )
        self.continue_loss.toggled.connect(self._invalidate)
        policy.addWidget(self.continue_loss)
        self.aux = QCheckBox("Auxiliary cutoff verified")
        self.aux.setToolTip(
            "Enable F events only after verifying dedicated outputs, safe OFF PWM, firmware mask and independent cutoff."
        )
        self.aux.toggled.connect(self._invalidate)
        policy.addWidget(self.aux)
        root.addLayout(policy)
        warning = QLabel(
            "HOLD does not disarm or guarantee accessory OFF. Keep RC takeover and an independent cutoff available."
        )
        warning.setWordWrap(True)
        warning.setObjectName("Warn")
        root.addWidget(warning)
        row = QHBoxLayout()
        self.upload_btn = QPushButton("Upload & verify")
        self.start_btn = QPushButton("Start mission")
        self.hold_btn = QPushButton("HOLD")
        self.hold_btn.setObjectName("Danger")
        self.upload_btn.clicked.connect(lambda: self._submit("upload"))
        self.start_btn.clicked.connect(lambda: self._submit("start"))
        self.hold_btn.clicked.connect(self._hold)
        for w in (self.upload_btn, self.start_btn, self.hold_btn):
            row.addWidget(w)
        root.addLayout(row)
        self.help_panel = QWidget()
        help_layout = QVBoxLayout(self.help_panel)
        help_layout.setContentsMargins(0, 0, 0, 0)
        help_text = QLabel(
            "Use a matching Mission v0.2.0 BASE/ROVER/NODE set. One active rover per session. "
            "Plan offline; Connect also works without a plan for HOLD recovery. Upload while DISARMED in MANUAL/HOLD; "
            "full readback is required. Arm using RC, then review and confirm Start. "
            "F events use a stopped mission delay after arrival; output telemetry and physical OFF are not verified. "
            "No auto-arm, reconnect or resume. Closing stops host heartbeats; the verified FC loss policy applies. "
            "A missing START reply or unconfirmed HOLD means state unknown. Wait 5 seconds between rover sessions."
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(150)
        self.log.setMaximumHeight(100)
        help_layout.addWidget(self.log)
        root.addWidget(self.help_panel)
        self.help_panel.setMaximumHeight(190)
        self.help_panel.hide()
        self.help_toggle.toggled.connect(self.help_panel.setVisible)
        self.map.location.connect(self._add)
        e = self.service.events
        e.message.connect(self._message)
        e.snapshot.connect(self._snapshot)
        e.ready.connect(self._ready)
        e.verified.connect(self._verified)
        e.busy.connect(self._busy)
        e.phase.connect(self._phase)
        e.capabilities.connect(self._capabilities)
        self.draft_timer = QTimer(self)
        self.draft_timer.setSingleShot(True)
        self.draft_timer.timeout.connect(self._save_draft)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._pulse)
        self.timer.start(100)
        self._restore_draft()
        self._invalidate()
        self._selected_rover = self.rover.value()
        self.rover.valueChanged.connect(self._switch_rover)

    def _switch_rover(self, rover):
        # Selection is normally disabled while connected. Guard programmatic
        # changes too: a selection event must never retarget an active worker.
        if self.service.running:
            self.rover.blockSignals(True)
            self.rover.setValue(self._selected_rover)
            self.rover.blockSignals(False)
            return
        self.draft_timer.stop()
        self._save_draft()
        self._selected_rover = rover
        if self._fleet_root is not None:
            self._draft_path = fleet_draft_path(self._fleet_root, rover)
        else:
            # Explicitly injected test/export paths also receive isolated files.
            self._draft_path = self._draft_path.parent / f"rover-{rover:03d}.json"
        self.digest = ""
        self.connected = False
        self.busy = False
        self._last_snapshot = None
        self.map._snapshot = None
        self.map._track.clear()
        self.map._home = None
        self.map._last_timestamp = None
        self.map._last_position = None
        self.continue_loss.setChecked(False)
        self.aux.setChecked(False)
        self.imported = None
        self.plan = Plan()
        self.speed.setValue(0.5)
        for ch, off, on in self.functions:
            ch.setValue(0)
            off.setValue(1100)
            on.setValue(1900)
        self._restore_draft()
        self._render()
        self._invalidate()
        self._phase(f"Rover {rover} · Planning offline")
        self._update_telemetry()

    def _pulse(self):
        self.service.pulse()
        self._controls()
        self._update_telemetry()

    def _message(self, text):
        self.log.appendPlainText(text)
        self.status.setToolTip(text)
        if self._phase_text == "Planning" and not self.service.running:
            self.status.setText(text[:120])

    def _snapshot(self, snapshot):
        if snapshot.vehicle_system != self.rover.value():
            return
        self._last_snapshot = snapshot
        self.map.set_snapshot(snapshot)
        self._update_telemetry()
        if snapshot.last_heartbeat:
            self.close_btn.setToolTip(
                f"Rover {snapshot.vehicle_system}: {snapshot.mode}, "
                + ("ARMED" if snapshot.armed else "DISARMED")
            )

    def _ready(self, ready):
        self.connected = ready
        if not ready:
            self.firmware_label.setText("BASE firmware: not connected")
        self._controls()

    def _verified(self, digest):
        self.digest = digest
        self._controls()

    def _busy(self, busy):
        self.busy = busy
        self._controls()

    def _invalidate(self, *_):
        self.digest = ""
        try:
            self._items_cache = parse_text(self._text())
            self._plan_valid = True
            self._plan_error = ""
        except (ValueError, TypeError, IndexError) as exc:
            self._items_cache = []
            self._plan_valid = False
            self._plan_error = str(exc)
        self._controls()
        if hasattr(self, "draft_timer") and not self.service.running:
            self.draft_timer.start(300)

    def _phase(self, text):
        self._phase_text = text
        self.status.setText(text)

    def _capabilities(self, values):
        route = "Direct" if not values["relays"] else f"{values['relays']} relay(s)"
        profile = values.get('profile')
        description = profile.description if profile else f"Mission {values['firmware']} · {route}"
        self.connect_btn.setToolTip(description)
        self.port.setToolTip(description + ' · one selected rover per session')
        self.firmware_label.setText(description)

    def _update_telemetry(self):
        s = self._last_snapshot
        if s is None or s.last_heartbeat is None:
            self.telemetry.setText("No FC telemetry")
            return
        age = max(0, time.monotonic() - s.last_heartbeat)
        state = "ARMED" if s.armed else "Disarmed"
        fresh = f"HB {age:.1f}s" if s.running and age <= 5 else "Telemetry stale"
        self.telemetry.setText(
            f"Rover {s.vehicle_system} · {s.mode} · {state} · {fresh}"
        )

    def _restore_draft(self):
        try:
            if self._draft_path.stat().st_size > 120000:
                raise ValueError("Draft exceeds size limit")
            data = json.loads(self._draft_path.read_text(encoding="utf-8"))
            if data.get("version") != 1:
                raise ValueError("Unsupported draft version")
            if data.get("wpl") is not None:
                parse_text(data["wpl"])
                self.imported = data["wpl"]
            else:
                points = data["points"]
                if len(points) > 60:
                    raise ValueError("Draft exceeds point limit")
                restored = []
                for point in points:
                    lat, lon = float(point[0]), float(point[1])
                    if (
                        not math.isfinite(lat)
                        or not math.isfinite(lon)
                        or not -85 <= lat <= 85
                        or not -180 <= lon <= 180
                    ):
                        raise ValueError("Invalid draft location")
                    actions = point[2]
                    if len(actions) > 3 or any(
                        type(a[0]) is not int
                        or a[0] not in range(3)
                        or type(a[1]) is not bool
                        for a in actions
                    ):
                        raise ValueError("Invalid draft actions")
                    restored.append(Point(lat, lon, [(a[0], a[1]) for a in actions]))
                self.plan.points = restored
                bindings = data["functions"]
                if len(bindings) != 3:
                    raise ValueError("Invalid function bindings")
                for widgets, values in zip(self.functions, bindings):
                    if len(values) != 3 or not all(type(v) is int for v in values):
                        raise ValueError("Invalid function values")
                    for widget, value in zip(widgets, values):
                        if not widget.minimum() <= value <= widget.maximum():
                            raise ValueError("Output value outside range")
                        widget.setValue(value)
                speed = float(data["speed"])
                if not math.isfinite(speed) or not 0.1 <= speed <= 3:
                    raise ValueError("Invalid draft speed")
                self.speed.setValue(speed)
            self._render()
            if self.map.points:
                self.map._center = self.map.points[0]
                self.map._follow = False
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            self.imported = None
            self.plan = Plan()
            self._render()
            self._message("Saved draft could not be restored; rebuild the route")

    def _save_draft(self):
        data = dict(
            version=1,
            wpl=self.imported,
            points=[[p.latitude, p.longitude, p.actions] for p in self.plan.points],
            functions=[[w.value() for w in row] for row in self.functions],
            speed=self.speed.value(),
        )
        try:
            text = json.dumps(data, allow_nan=False)
            self._draft_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._draft_path.with_suffix(".tmp")
            temp.write_text(text, encoding="utf-8")
            temp.replace(self._draft_path)
        except (OSError, ValueError):
            self._message("Draft could not be saved; use Export WPL")

    def _controls(self):
        running = self.service.running
        self.port.setEnabled(not running)
        self.rover.setEnabled(not running)
        self.refresh_btn.setEnabled(not running)
        self.connect_btn.setEnabled(
            not running and time.monotonic() >= self.service.quiet_until
        )
        self.close_btn.setEnabled(running)
        for widget in self._editing_controls:
            widget.setEnabled(not running)
        self.continue_loss.setEnabled(not running)
        self.aux.setEnabled(not running)
        aux_needed = any(
            row["command"] == 183 for row in getattr(self, "_items_cache", [])
        )
        allowed = self._plan_valid and (not aux_needed or self.aux.isChecked())
        s = self._last_snapshot
        fresh = (
            s is not None
            and s.last_heartbeat is not None
            and s.running
            and 0 <= time.monotonic() - s.last_heartbeat <= 5
        )
        editable_fc = fresh and not s.armed and s.mode in ("MANUAL", "HOLD")
        self.upload_btn.setEnabled(
            self.connected and running and not self.busy and allowed and editable_fc
        )
        self.upload_btn.setToolTip(
            getattr(self, "_plan_error", "")
            or (
                "Verify the auxiliary cutoff before connecting"
                if aux_needed and not self.aux.isChecked()
                else "Upload, then compare every stored mission row"
            )
        )
        self.start_btn.setEnabled(
            self.connected
            and running
            and not self.busy
            and bool(self.digest)
            and fresh
            and s.armed
            and s.mode in ("MANUAL", "HOLD")
        )
        self.hold_btn.setEnabled(self.connected and running)

    def _center(self):
        if abs(self.lat.value()) < 1e-7 and abs(self.lon.value()) < 1e-7:
            self._message(
                "Enter reviewed coordinates or import a route to center the planning map"
            )
            return
        self.map._center = (self.lat.value(), self.lon.value())
        self.map._follow = False
        self.map.update()

    def _add(self, lat, lon):
        if self.service.running:
            return
        if self.imported is not None:
            self._message("Clear the imported WPL before editing a new map route")
            return
        if len(self.plan.points) >= 60:
            return
        if abs(lat) < 1e-7 and abs(lon) < 1e-7:
            self._message(
                "Choose a reviewed location; zero latitude AND longitude rejected"
            )
            return
        action = self.mode.currentData()
        actions = [] if action is None else [action]
        self.plan.points.append(Point(lat, lon, actions))
        self.mode.setCurrentIndex(0)
        self.lat.setValue(lat)
        self.lon.setValue(lon)
        self._render()
        self._invalidate()

    def _render(self):
        self.rows.clear()
        if self.imported is not None:
            for r in parse_text(self.imported)[1:]:
                detail = (
                    f"{r['x'] / 1e7:.7f}, {r['y'] / 1e7:.7f}"
                    if r["command"] == 16
                    else str(r["params"])
                )
                self.rows.addItem(f"{r['seq']} · CMD {r['command']} · {detail}")
            self.map.points = [
                (r["x"] / 1e7, r["y"] / 1e7)
                for r in parse_text(self.imported)[1:]
                if r["command"] == 16
            ]
        else:
            for i, p in enumerate(self.plan.points):
                label = ", ".join(
                    f"F{f + 1} " + ("ON" if on else "OFF") for f, on in p.actions
                )
                self.rows.addItem(
                    f"{i + 1} · {p.latitude:.7f}, {p.longitude:.7f} {label}"
                )
            self.map.points = [(p.latitude, p.longitude) for p in self.plan.points]
        self.map.update()

    def _move(self, delta):
        if self.service.running:
            return
        if self.imported is not None:
            return
        i = self.rows.currentRow()
        j = i + delta
        if 0 <= i < len(self.plan.points) and 0 <= j < len(self.plan.points):
            self.plan.points[i], self.plan.points[j] = (
                self.plan.points[j],
                self.plan.points[i],
            )
            self._render()
            self.rows.setCurrentRow(j)
            self._invalidate()

    def _remove(self):
        if self.service.running:
            return
        if self.imported is None and 0 <= self.rows.currentRow() < len(
            self.plan.points
        ):
            del self.plan.points[self.rows.currentRow()]
            self._render()
            self._invalidate()

    def _clear(self):
        if self.service.running:
            return
        self.imported = None
        self.plan.points.clear()
        self._render()
        self._invalidate()

    def _text(self):
        if self.imported is not None:
            return self.imported
        self.plan.functions = [
            Function(ch.value(), off.value(), on.value())
            for ch, off, on in self.functions
        ]
        self.plan.speed = self.speed.value()
        return self.plan.wpl()

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import QGC WPL 110", "", "Waypoints (*.waypoints *.txt)"
        )
        if not path:
            return
        try:
            if Path(path).stat().st_size > 100000:
                raise ValueError("Plan file too large")
            text = Path(path).read_text(encoding="utf-8")
            items = parse_text(text)
            self.imported = text
            self._render()
            self._invalidate()
            p = next((r for r in items[1:] if r["command"] == 16), None)
            if p:
                self.map._center = (p["x"] / 1e7, p["y"] / 1e7)
                self.map._follow = False
                self.map.update()
        except (OSError, ValueError) as exc:
            self._message(str(exc))

    def _export(self):
        try:
            text = self._text()
            parse_text(text)
        except ValueError as exc:
            self._message(str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export reviewed route", "", "Waypoints (*.waypoints)"
        )
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                self._message("Plan exported; no connection or command sent")
            except OSError as exc:
                self._message(str(exc))

    def _connect(self):
        try:
            if not self.port.currentText().strip():
                raise ValueError("Select the BASE COM port")
            if not self.prepare_link():
                return
            self.service.connect(self.port.currentText().strip(), self.rover.value())
            self._controls()
        except (RuntimeError, ValueError) as exc:
            self._message(str(exc))

    def _disconnect(self):
        if not self.service.close():
            self._message("Closing the mission link; reconnect remains locked")
            return
        self.digest = ""
        self.connected = False
        self._message(
            "Disconnected. Mission/auxiliary state UNKNOWN; FC loss profile applies. Use RC/physical stop as needed."
        )
        self._controls()

    def _submit(self, action):
        try:
            items = parse_text(self._text())
            rover = self.rover.value()
            digest = fingerprint(items, rover)
            if action == "start" and self.digest != digest:
                raise ValueError("Exact plan must be uploaded and verified first")
            phrase = (
                f"{'UPLOAD' if action == 'upload' else 'START'} {rover} {digest[:12]}"
            )
            policy = (
                "CONTINUE onboard AUTO on link loss"
                if self.continue_loss.isChecked()
                else "HOLD on GCS loss"
            )
            review = "\n".join(
                f"{r['seq']}: CMD {r['command']} {r['params']} {r['x'] / 1e7:.7f}, {r['y'] / 1e7:.7f}"
                for r in items[1:]
            )
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Review {action.upper()} · Rover {rover}")
            layout = QVBoxLayout(dialog)
            heading = QLabel(
                f"Rover {rover}; {len(items) - 1} action rows; {policy}.\n"
                f"{'Replaces the stored mission. Rover must be DISARMED MANUAL/HOLD.' if action == 'upload' else 'Arm with RC in MANUAL/HOLD. START is sent once; a missing ACK means UNKNOWN.'}\n"
                "Review the exact route/actions below. HOLD does not guarantee accessory OFF.\n"
                f"Type {phrase}"
            )
            heading.setWordWrap(True)
            layout.addWidget(heading)
            preview = QPlainTextEdit(review)
            preview.setReadOnly(True)
            layout.addWidget(preview)
            confirmation = QLineEdit()
            confirmation.setObjectName("missionConfirmation")
            layout.addWidget(confirmation)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            )
            accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
            accept.setText("Upload" if action == "upload" else "Start mission")
            accept.setEnabled(False)
            confirmation.textChanged.connect(
                lambda value: accept.setEnabled(value.strip() == phrase)
            )
            hold = buttons.addButton("HOLD", QDialogButtonBox.ButtonRole.ActionRole)
            hold.clicked.connect(lambda: (self._hold(), dialog.reject()))
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            dialog.resize(800, 450)
            if (
                dialog.exec() != QDialog.DialogCode.Accepted
                or confirmation.text().strip() != phrase
            ):
                return
            if not self.connected or self.busy or not self.service.running:
                raise RuntimeError("Session changed during confirmation")
            self.service.submit(
                action, items, self.continue_loss.isChecked(), self.aux.isChecked()
            )
            self.busy = True
            self._controls()
        except (ValueError, RuntimeError, queue.Full) as exc:
            self._message(str(exc))

    def _hold(self):
        self.digest = ""
        self.service.hold()
        self._message(
            "HOLD requested; awaiting fresh FC HOLD heartbeat. Auxiliary OFF is NOT confirmed."
        )
        self._controls()

    def _shutdown(self):
        if getattr(self, "_shutdown_complete", False):
            return True
        if not self.service.close():
            self._message("Mission worker is still closing; try closing again")
            return False
        self.draft_timer.stop()
        self._save_draft()
        self.connected = False
        self.digest = ""
        self.timer.stop()
        self.map.shutdown()
        self._shutdown_complete = True
        return True

    def done(self, result):
        if self._shutdown():
            super().done(result)

    def closeEvent(self, event):
        if not self._shutdown():
            event.ignore()
            return
        super().closeEvent(event)
