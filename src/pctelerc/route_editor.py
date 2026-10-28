"""Planning gestures only. No transport or vehicle-command access."""
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QMenu, QLabel, QWidgetAction, QWidget, QVBoxLayout
from .rover_map import world_pixel, world_location
from .route_popups import choose_hold
from .theme import MENU_STYLE


class RouteEditor:
    def init_editor(self):
        self.route_editable = False
        self.route_kinds = []
        self.planned_home = None
        self._route_gesture = None
        self._route_preview = None
        self._route_menu = None
        self._route_revision = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def cancel_route_edit(self):
        self._route_gesture = None
        self._route_preview = None
        self.update()

    def cancel_pan(self):
        if getattr(self, '_route_gesture', None) is not None:
            self.cancel_route_edit()
        super().cancel_pan()

    def set_route(self, points, kinds, home, editable):
        state = (list(points), list(kinds), home, bool(editable))
        old = (self.points, self.route_kinds, self.planned_home, self.route_editable)
        if state != old:
            self._route_revision += 1
            self.cancel_route_edit()
            if self._route_menu is not None:
                self._route_menu.close()
            self.points, self.route_kinds, self.planned_home, self.route_editable = state
            self.update()

    def route_location(self, position):
        x, y = world_pixel(*self._center, self._zoom)
        return world_location(x+position.x()-self.width()/2,
                              y+position.y()-self.height()/2, self._zoom)

    def route_hit(self, position):
        for i, point in enumerate(self.points):
            if (self.project(point)-position).manhattanLength() <= 19:
                return "point", i
        for i in range(1, len(self.points)):
            a, b = self.project(self.points[i-1]), self.project(self.points[i])
            delta = b-a
            length = delta.x()**2+delta.y()**2
            if not length:
                continue
            t = ((position.x()-a.x())*delta.x()+(position.y()-a.y())*delta.y())/length
            if .08 < t < .92:
                nearest = a+delta*t
                if (nearest-position).manhattanLength() <= 10:
                    return "line", i
        return None

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton and self.route_editable
                and self._center is not None):
            hit = self.route_hit(event.position())
            if hit is not None:
                self.cancel_pan()
                self._route_gesture = (hit, QPointF(event.position()), False)
                self.setFocus()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._route_gesture is None:
            return super().mouseMoveEvent(event)
        if not self.route_editable or not event.buttons() & Qt.MouseButton.LeftButton:
            self.cancel_route_edit()
            return
        hit, origin, moved = self._route_gesture
        moved = moved or (event.position()-origin).manhattanLength() >= self.DRAG_THRESHOLD
        self._route_gesture = hit, origin, moved
        if moved:
            self._manual_view()
            self._route_preview = list(self.points)
            kind, index = hit
            point = self.route_location(event.position())
            if kind == "line":
                self._route_preview.insert(index, point)
            elif self.route_kinds[index] != "rth":
                self._route_preview[index] = point
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._route_gesture is None:
            return super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit, origin, moved = self._route_gesture
        moved = moved or (event.position()-origin).manhattanLength() >= self.DRAG_THRESHOLD
        self.cancel_route_edit()
        if self.route_editable and self.rect().contains(event.position().toPoint()):
            kind, index = hit
            lat, lon = self.route_location(event.position())
            if moved:
                self._manual_view()
                if kind == "line":
                    self.route_inserted.emit(index, lat, lon)
                elif self.route_kinds[index] != "rth":
                    self.route_moved.emit(index, lat, lon)
            elif kind == "point":
                self.show_route_menu(*self.points[index], index)
        event.accept()

    def show_route_menu(self, lat, lon, index=-1):
        if not self.route_editable:
            return
        self.cancel_pan()
        self.cancel_route_edit()
        if self._route_menu is not None:
            self._route_menu.close()
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.setToolTipsVisible(True)
        menu.setObjectName("RouteActions")
        header = QWidgetAction(menu)
        header_widget = QWidget()
        header_widget.setStyleSheet('background:transparent;')
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(16,8,16,9);header_layout.setSpacing(5)
        title = QLabel(f'Rover {self.selected_rover} · '+(f'Waypoint {index+1}' if index >= 0 else 'Route'))
        title.setStyleSheet('color:#e8eef6; font-size:13px; font-weight:600; background:transparent;')
        coordinates = QLabel(f'{lat:.6f}, {lon:.6f}')
        coordinates.setStyleSheet('color:#a4b2c4; font-size:11px; background:transparent;')
        header_layout.addWidget(title);header_layout.addWidget(coordinates)
        header.setDefaultWidget(header_widget);menu.addAction(header);menu.addSeparator()
        rover, revision = self.selected_rover, self._route_revision
        def emit(name, value=5):
            if self.route_editable and self.selected_rover == rover and self._route_revision == revision:
                self.route_action.emit(name, lat, lon, index, value)
        def action(label, name, value=5):
            item = menu.addAction(label)
            item.setData(name)
            item.triggered.connect(lambda: emit(name, value))
            return item
        action("Go here" if index < 0 else "Waypoint", "go").setToolTip("Add or update an offline waypoint; no movement command is sent")
        hold = menu.addAction("Hold on arrival…")
        hold.setData("hold")
        def apply_hold():
            # Capture identity: a dialog must never edit a newly selected rover.
            seconds, ok = choose_hold(self)
            if ok:
                emit("hold", seconds)
        hold.triggered.connect(apply_hold)
        rth = action("Return home", "rth")
        rth.setEnabled(self.planned_home is not None and "rth" not in self.route_kinds)
        rth.setToolTip("Adds a final waypoint at the marked planning home; does not change FC RTL mode")
        menu.addSeparator()
        action("Set planned home", "home")
        if index >= 0:
            action("Remove waypoint", "remove")
        self._route_menu = menu
        menu.aboutToHide.connect(lambda: menu.deleteLater())
        menu.destroyed.connect(lambda: self._menu_closed(menu))
        menu.popup(self.mapToGlobal(self.project((lat, lon)).toPoint()))

    def _menu_closed(self, menu):
        if self._route_menu is menu:
            self._route_menu = None

    def contextMenuEvent(self, event):
        if self._center is not None:
            hit = self.route_hit(QPointF(event.pos()))
            index = hit[1] if hit is not None and hit[0] == "point" else -1
            point = self.points[index] if index >= 0 else self.route_location(QPointF(event.pos()))
            self.show_route_menu(*point, index)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_route_edit()
            self.cancel_pan()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        self.cancel_route_edit()
        super().wheelEvent(event)

    def event(self, event):
        if event.type() in (QEvent.Type.UngrabMouse, QEvent.Type.WindowDeactivate,
                            QEvent.Type.Hide, QEvent.Type.Resize):
            if getattr(self, "_route_gesture", None) is not None:
                self.cancel_route_edit()
        return super().event(event)

    def _paint_overlays(self, painter):
        original = self.points
        if self._route_preview is not None:
            self.points = self._route_preview
        try:
            super()._paint_overlays(painter)
            shown = self.points
        finally:
            self.points = original
        if self._center is None:
            return
        painter.setPen(QPen(QColor("#d7b670"), 2))
        for i, point in enumerate(shown):
            p = self.project(point)
            if i:
                midpoint = (self.project(shown[i-1])+p)/2
                painter.setBrush(QColor("#d7b670"))
                painter.drawEllipse(midpoint, 3, 3)
            if self._route_preview is None and i < len(self.route_kinds):
                caption = {"hold":"Hold", "rth":"RTH"}.get(self.route_kinds[i])
                if caption:
                    painter.drawText(p+QPointF(15, -7), caption)
        if self.planned_home is not None:
            p = self.project(self.planned_home)
            painter.setBrush(QColor("#102640"))
            painter.setPen(QPen(QColor("#d8e4f1"), 2))
            painter.drawRoundedRect(p.x()-12, p.y()-30, 24, 22, 4, 4)
            painter.drawText(p+QPointF(-5, -14), "H")
            width = painter.fontMetrics().horizontalAdvance('Planned home')
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#192534'))
            painter.drawRoundedRect(p.x()-width-22,p.y()-34,width+8,20,4,4)
            painter.setPen(QColor('#e8eef6'))
            painter.drawText(p+QPointF(-width-18, -19), "Planned home")
