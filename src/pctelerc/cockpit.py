"""Persistent camera/map surfaces: resize and swap without restarting media."""
from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect
from PySide6.QtWidgets import QWidget


class Cockpit(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self.primary_map = False
        self.minimized = False
        self.camera = self.map_panel = self.restore = None
        self._transition = QParallelAnimationGroup(self)

    def set_views(self, camera, map_panel, restore):
        self.camera, self.map_panel, self.restore = camera, map_panel, restore
        for view in (camera, map_panel, restore):
            view.setParent(self)
        camera.setMinimumSize(0, 0)
        map_panel.setMinimumSize(0, 0)
        self.arrange()

    def arrange(self, *, animate=False):
        if self.camera is None:
            return
        self._transition.stop()
        self._transition.deleteLater()
        self._transition = QParallelAnimationGroup(self)
        width, height = self.width(), self.height()
        inset_width = min(282, max(230, width // 3))
        inset_height = min(214, max(180, height // 2))
        inset = QRect(0, max(0, height - inset_height), inset_width, inset_height)
        full = self.rect()
        camera_rect, map_rect = full, inset
        if self.primary_map:
            map_rect = full
            camera_rect = QRect(6, max(0, height - inset_height - 44), inset_width, inset_height)
        self.map_panel.setVisible(not self.minimized)
        self.restore.setVisible(self.minimized)
        for view, target in ((self.camera, camera_rect), (self.map_panel, map_rect)):
            if animate and self.isVisible():
                animation = QPropertyAnimation(view, b"geometry", self._transition)
                animation.setDuration(160)
                animation.setStartValue(view.geometry())
                animation.setEndValue(target)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._transition.addAnimation(animation)
            else:
                view.setGeometry(target)
        (self.camera if self.primary_map else self.map_panel).raise_()
        self.restore.setGeometry(0, max(0, height - 32), 92, 32)
        self.restore.raise_()
        if animate:
            self._transition.start()

    def resizeEvent(self, event):
        self.arrange()
        super().resizeEvent(event)
