"""Map route editor and explicit LoRa mission commissioning UI."""

from pathlib import Path
import json
import math
import queue
import time

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPen, QShortcut, QKeySequence
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
    QSizePolicy,
    QLayout,
)

from .mission_plan import Plan, Point, Function, parse_text
from .mission_protocol.client import fingerprint
from .mission_service import MissionService
from .rover_map import RoverMap, world_pixel, world_location
from .lora_setup_widget import refresh_ports
from .config import data_dir
from .fleet import draft_path as fleet_draft_path
from .route_draft import decode as decode_draft, MAX_BYTES


class MissionMap(RoverMap):
    location = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.press = None
        self.moved = False
        self.setMinimumSize(350, 250)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press = QPointF(event.position())
            self.moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.moved = self._dragging

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        super().mouseReleaseEvent(event)
        if (self.press is not None and not self._last_dragged and self._center is not None
                and self.rect().contains(event.position().toPoint())):
            x, y = world_pixel(*self._center, self._zoom)
            x += event.position().x() - self.width() / 2
            y += event.position().y() - self.height() / 2
            lat, lon = world_location(x, y, self._zoom)
            self.location.emit(lat, lon)
        self.press = None

    def _paint_overlays(self, painter):
        super()._paint_overlays(painter)
        if self._center is None:
            return
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
    def __init__(self, prepare_link, parent=None, service=None, draft_path=None, *, embedded=False, rover_id=1):
        super().__init__(parent)
        self.embedded = embedded
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
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
        if embedded:
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(6)
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
        self.import_btn = QPushButton("Import route")
        self.export_btn = QPushButton("Export route")
        self.import_btn.setToolTip("Restore an editable TeleRC plan or import read-only QGC WPL")
        self.export_btn.setToolTip("Save an editable TeleRC plan, or QGC WPL for mission interchange")
        self.import_btn.clicked.connect(self._import)
        self.export_btn.clicked.connect(self._export)
        if embedded:
            files = QHBoxLayout()
            files.addWidget(self.import_btn)
            files.addWidget(self.export_btn)
            root.addLayout(files)
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
        self.rover.setValue(rover_id)
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
        self.link_controls = QWidget()
        self.link_controls.setLayout(link)
        root.addWidget(self.link_controls)
        self.link_controls.setVisible(not embedded)
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
        self.editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        if embedded:
            self.setMinimumSize(300,0)
            self.editor_scroll.setMinimumWidth(0)
            self.editor.setMinimumWidth(0)
            self.editor.setMinimumHeight(0)
            # QScrollArea must grow content vertically, never promote native
            # Windows minimum-size hints into a wider, clipped child widget.
            self.editor.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
            el.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
            body.setMinimumHeight(120)
            body.setChildrenCollapsible(False)
            self.map.hide()
            self.map.set_online(False)
            self.map._timer.stop()
            self.plan_toggle.hide()
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
        coords.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        coords.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
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
        self.rows.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rows.setTextElideMode(Qt.TextElideMode.ElideRight)
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
            if embedded:
                b.ensurePolished()
                b.setMinimumWidth(b.fontMetrics().horizontalAdvance(label)+18)
            row.addWidget(b)
            self._editing_controls.append(b)
        el.addLayout(row)
        history = QHBoxLayout()
        self.undo_btn = QPushButton("Undo")
        self.redo_btn = QPushButton("Redo")
        self.undo_btn.setToolTip("Undo this rover's offline draft edit (Ctrl+Z)")
        self.redo_btn.setToolTip("Redo this rover's offline draft edit (Ctrl+Y / Ctrl+Shift+Z)")
        self.undo_btn.clicked.connect(lambda: self._history_step(-1))
        self.redo_btn.clicked.connect(lambda: self._history_step(1))
        history.addWidget(self.undo_btn);history.addWidget(self.redo_btn)
        el.addLayout(history)
        if not embedded:
            for key, direction in (("Ctrl+Z", -1), ("Ctrl+Y", 1), ("Ctrl+Shift+Z", 1)):
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                shortcut.activated.connect(lambda d=direction: self._history_step(d))
        self.advanced_toggle = QPushButton("Output settings")
        self.advanced_toggle.setCheckable(True)
        el.addWidget(self.advanced_toggle)
        self.output_settings = QWidget()
        output_layout = QVBoxLayout(self.output_settings)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_settings.hide()
        self.advanced_toggle.toggled.connect(self.output_settings.setVisible)
        self.advanced_toggle.toggled.connect(
            lambda expanded: self.editor.setMinimumHeight(0 if embedded else 550 if expanded else 410)
        )
        output_layout.addWidget(QLabel("F1–F3 · dedicated auxiliary outputs"))
        self.functions = []
        for i in range(3):
            # Native Windows spin-box arrows and minimum size hints are wider
            # than the Linux style. A form remains readable in the narrow pane
            # instead of forcing all three numeric fields onto one clipped row.
            row = QFormLayout()
            row.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
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
            for label,w in ((f"F{i + 1} output",ch),("OFF (µs)",off),("ON (µs)",on)):
                row.addRow(label,w)
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
        if not embedded:
            row = QHBoxLayout()
            row.addWidget(self.import_btn)
            row.addWidget(self.export_btn)
            el.addLayout(row)
        self._editing_controls += [self.mode, self.lat, self.lon, add, self.import_btn, self.speed]
        self._editing_controls += [w for row in self.functions for w in row]
        for widget in [
            self.lat,
            self.lon,
            self.speed,
            *[w for row in self.functions for w in row],
        ]:
            widget.setMinimumHeight(28)
        policy = QVBoxLayout() if embedded else QHBoxLayout()
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
        if embedded:
            warning.setText('HOLD leaves accessory state unconfirmed.')
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
        if embedded:
            self.start_btn.hide()
            help_text.setText('Upload disarmed and verify the exact route. Use this rover’s Arm and Mission start buttons. '
                'Disarm requests HOLD, confirms stationary telemetry, then sends normal disarm. '
                'The BASE polls connected rovers fairly within a measured airtime budget. '
                'Stale labels are last-known positions. No automatic arm, start, reconnect or replay. '
                'FPV is provided by external monitors. HOLD does not confirm accessory OFF.')
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
        self._history = [self._draft_text()]
        self._history_index = 0
        self._history_paused = False
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
        self._history_paused = True
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
        self._history = [self._draft_text()]
        self._history_index = 0
        self._history_paused = False
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
        self._record_history()
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

    def _draft_text(self):
        return json.dumps(dict(version=1, wpl=self.imported,
            points=[[p.latitude,p.longitude,p.actions,p.kind,p.hold_seconds] for p in self.plan.points],
            home=self.plan.home, functions=[[w.value() for w in row] for row in self.functions],
            speed=self.speed.value()), allow_nan=False)

    def _apply_draft(self, data):
        # Decode completely before applying anything; suppress intermediate
        # value signals so restore/undo is a single planning transaction.
        blockers = [QSignalBlocker(w) for w in (self.speed, self.aux, *[w for row in self.functions for w in row])]
        self.imported = data['wpl']
        self.plan = Plan(points=[Point(p[0],p[1],[(a[0],a[1]) for a in p[2]],p[3],p[4]) for p in data['points']],
            home=None if data['home'] is None else tuple(data['home']))
        for widgets, values in zip(self.functions,data['functions']):
            for w, value in zip(widgets,values):w.setValue(value)
        self.speed.setValue(data['speed'])
        self.aux.setChecked(False)
        del blockers
        self._render()

    def _record_history(self):
        if not hasattr(self, '_history') or self._history_paused or self.service.running:
            return
        state = self._draft_text()
        if state != self._history[self._history_index]:
            del self._history[self._history_index+1:]
            self._history.append(state)
            # At most 50 reversible edits per rover, never telemetry or commands.
            if len(self._history) > 51:self._history.pop(0)
            self._history_index = len(self._history)-1

    def _history_step(self, delta):
        if self.service.running or self.busy or delta not in (-1,1):return
        index = self._history_index+delta
        if not 0 <= index < len(self._history):return
        self._history_paused = True
        try:
            self._apply_draft(decode_draft(self._history[index]))
            self._history_index = index
            self._invalidate()
        finally:
            self._history_paused = False
        self._message('Draft edit undone' if delta < 0 else 'Draft edit redone')

    def _restore_draft(self):
        try:
            if self._draft_path.stat().st_size > MAX_BYTES:raise ValueError('Draft exceeds size limit')
            self._apply_draft(decode_draft(self._draft_path.read_text(encoding='utf-8')))
            if self.map.points:
                self.map._center = self.map.points[0]
                self.map._follow = False
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError):
            self.imported = None
            self.plan = Plan()
            self._render()
            self._message('Saved draft could not be restored; rebuild or import the route')

    def _save_draft(self):
        try:
            text = self._draft_text()
            self._draft_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._draft_path.with_suffix('.tmp')
            temp.write_text(text, encoding='utf-8')
            temp.replace(self._draft_path)
            return True
        except (OSError, ValueError):
            self._message('Draft could not be saved; use Export route')
            return False

    def _controls(self):
        running = self.service.running
        self.port.setEnabled(not running)
        self.rover.setEnabled(not running)
        self.refresh_btn.setEnabled(not running)
        self.connect_btn.setEnabled(
            not running and time.monotonic() >= self.service.quiet_until
        )
        self.close_btn.setEnabled(running)
        self.undo_btn.setEnabled(not running and not self.busy and getattr(self, '_history_index', 0) > 0)
        self.redo_btn.setEnabled(not running and not self.busy
            and getattr(self, '_history_index', 0)+1 < len(getattr(self, '_history', [])))
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
            and (getattr(self.service,'operation_gate',None) is None or not self.service.operation_gate.locked())
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
        self.sync_external_route()

    def sync_external_route(self):
        if self.embedded and hasattr(self, 'external_map') and self.external_map.selected_rover == self.rover.value():
            self.external_map.set_route(self.map.points,
                [p.kind for p in self.plan.points] if self.imported is None else ['go']*len(self.map.points),
                self.plan.home if self.imported is None else None,
                not self.service.running and not self.busy and self.imported is None)

    @staticmethod
    def _valid_map_location(lat, lon):
        return (all(type(v) in (int,float) and math.isfinite(v) for v in (lat,lon))
            and -85 <= lat <= 85 and -180 <= lon <= 180
            and not (abs(lat) < 1e-7 and abs(lon) < 1e-7))

    def map_action(self, action, lat, lon, index=-1, seconds=5):
        """Change this offline draft; never emit a vehicle command."""
        if self.service.running or self.busy or self.imported is not None:
            return
        if not self._valid_map_location(lat, lon):
            self._message('Choose valid map coordinates')
            return
        if action == 'home':
            self.plan.home = (lat,lon)
            for p in self.plan.points:
                if p.kind == 'rth':
                    p.latitude,p.longitude = self.plan.home
        elif action == 'remove':
            if not 0 <= index < len(self.plan.points):return
            del self.plan.points[index]
        elif action == 'rth':
            if self.plan.home is None or len(self.plan.points) >= 60 or any(p.kind == 'rth' for p in self.plan.points):return
            self.plan.points.append(Point(*self.plan.home, kind='rth'))
        elif action in ('go','hold'):
            if action == 'hold' and (type(seconds) is not int or not 2 <= seconds <= 10):return
            if 0 <= index < len(self.plan.points):
                point = self.plan.points[index]
                point.kind,point.hold_seconds = action,seconds
            else:
                if len(self.plan.points) >= 60:return
                point = Point(lat,lon,kind=action,hold_seconds=seconds)
                # New map points stay before an existing final return leg.
                position = len(self.plan.points)-(bool(self.plan.points) and self.plan.points[-1].kind == 'rth')
                self.plan.points.insert(position,point)
            self.lat.setValue(lat);self.lon.setValue(lon)
        else:
            return
        self._render();self._invalidate()

    def move_map_point(self, index, lat, lon, *, insert=False):
        if (self.service.running or self.busy or self.imported is not None
                or not self._valid_map_location(lat, lon)):
            return
        if insert:
            if len(self.plan.points) >= 60 or not 1 <= index < len(self.plan.points):return
            self.plan.points.insert(index,Point(lat,lon))
        else:
            if not 0 <= index < len(self.plan.points) or self.plan.points[index].kind == 'rth':return
            self.plan.points[index].latitude,self.plan.points[index].longitude = lat,lon
        self._render();self.rows.setCurrentRow(index);self._invalidate()

    def _center(self):
        if abs(self.lat.value()) < 1e-7 and abs(self.lon.value()) < 1e-7:
            self._message(
                "Enter reviewed coordinates or import a route to center the planning map"
            )
            return
        self.map._center = (self.lat.value(), self.lon.value())
        self.map._follow = False
        self.map.update()

        if self.embedded and hasattr(self,'external_map'):
            self.external_map._center=self.map._center
            self.external_map.follow_rover=None
            self.external_map.auto_fit=False
            self.external_map.update()

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
        position = len(self.plan.points)-(bool(self.plan.points) and self.plan.points[-1].kind == 'rth')
        self.plan.points.insert(position, Point(lat, lon, actions))
        self.mode.setCurrentIndex(0)
        self.lat.setValue(lat)
        self.lon.setValue(lon)
        self._render()
        self._invalidate()

    def _render(self):
        selected = self.rows.currentRow()
        scroll = self.rows.verticalScrollBar().value()
        self.rows.setUpdatesEnabled(False)
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
                    f"{i + 1} · {p.latitude:.7f}, {p.longitude:.7f} "
                    + (f"Hold {p.hold_seconds}s " if p.kind == 'hold' else 'RTH · planned home ' if p.kind == 'rth' else '') + label
                )
            self.map.points = [(p.latitude, p.longitude) for p in self.plan.points]
        self.rows.setCurrentRow(min(selected, self.rows.count()-1))
        self.rows.verticalScrollBar().setValue(scroll)
        self.rows.setUpdatesEnabled(True)
        self.map.update()
        self.sync_external_route()

    def _move(self, delta):
        if self.service.running:
            return
        if self.imported is not None:
            return
        i = self.rows.currentRow()
        j = i + delta
        if 0 <= i < len(self.plan.points) and 0 <= j < len(self.plan.points):
            if self.plan.points[i].kind == 'rth' or self.plan.points[j].kind == 'rth':
                self._message('Return to planned home stays at the end of the route')
                return
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
        self.plan.home = None
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
        if self.service.running:
            self._message("Disconnect this rover before importing a route")
            return
        identity, revision = self.rover.value(), self._draft_text()
        path, _ = QFileDialog.getOpenFileName(
            self, "Import route", "", "TeleRC plan (*.telerc.json);;Waypoints (*.waypoints *.txt)"
        )
        if not path:
            return
        try:
            if Path(path).stat().st_size > MAX_BYTES:
                raise ValueError("Plan file too large")
            text = Path(path).read_text(encoding="utf-8")
            native = Path(path).suffix.lower() == '.json'
            data = decode_draft(text) if native else None
            if not native:parse_text(text)
            if (self.service.running or self.busy or self.rover.value() != identity
                    or self._draft_text() != revision
                    or (self.embedded and hasattr(self, 'external_map') and self.external_map.selected_rover != identity)):
                raise ValueError("Session changed; select the rover and import again")
            if native:self._apply_draft(data)
            else:
                self.imported = text
                self._render()
            self._invalidate()
            point = self.map.points[0] if self.map.points else None
            if point:
                self.map._center = point
                self.map._follow = False
                self.map.update()
                if self.embedded and hasattr(self, 'external_map') and self.external_map.selected_rover == self.rover.value():
                    self.external_map._center = self.map._center
                    self.external_map.follow_rover = None
                    self.external_map.auto_fit = False
                    self.external_map.update()
            self._message("Route imported into this rover's draft; review before upload")
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            self._message(str(exc))

    def _export(self):
        # Capture the draft before the file picker; nested Qt events must not
        # silently export another revision or newly selected rover.
        draft = self._draft_text()
        path, selected_filter = QFileDialog.getSaveFileName(
            self, 'Export route', '', 'TeleRC plan (*.telerc.json);;Waypoints (*.waypoints)')
        if not path:return
        temporary = None
        try:
            target = Path(path)
            native = target.suffix.lower() == '.json' or (not target.suffix and not selected_filter.startswith('Waypoints'))
            if not target.suffix:target = target.with_suffix('.telerc.json' if native else '.waypoints')
            if native:
                decode_draft(draft)
                text = draft
            else:
                data = decode_draft(draft)
                plan = Plan(points=[Point(p[0],p[1],[(a[0],a[1]) for a in p[2]],p[3],p[4]) for p in data['points']],
                    functions=[Function(*row) for row in data['functions']], speed=data['speed'],
                    home=None if data['home'] is None else tuple(data['home']))
                text = data['wpl'] if data['wpl'] is not None else plan.wpl()
                parse_text(text)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                    prefix='.'+target.name+'.', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                output.write(text)
            temporary.replace(target)
            self._message('Editable plan exported' if native else 'WPL exported; planned-home metadata is not included')
        except (OSError, ValueError) as exc:
            self._message(str(exc))
        finally:
            if temporary is not None:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass

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

    def keyPressEvent(self,event):
        if self.embedded and event.key()==Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._shutdown():
            event.ignore()
            return
        super().closeEvent(event)
