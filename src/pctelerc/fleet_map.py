"""A single fleet map; labels move only on genuine, addressed GPS samples."""
from collections import deque
import math
import time
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from .mission_widget import MissionMap
from .rover_map import position_fresh, world_pixel
from .route_editor import RouteEditor


class FleetMap(RouteEditor, MissionMap):
    route_action = Signal(str, float, float, int, int)
    route_moved = Signal(int, float, float)
    route_inserted = Signal(int, float, float)
    MAP_BACKGROUND = '#101924'
    MAP_TEXT = '#a4b2c4'
    MAP_CHROME = '#151e2a'
    COLORS = ('#71cfc5','#79b9f5','#e5c06e','#bca0f5','#f59cb7','#63d3e0','#f4ae79')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshots = {}
        self.positions = {}
        self.trails = {}
        self.selected_rover = 1
        self.follow_rover = None
        self.auto_fit = True
        self.init_editor()

    def observe(self,rover,snapshot):
        if snapshot.vehicle_system != rover or not 1 <= rover <= 20:
            return
        was_fresh = self.fresh(rover)
        old_snapshot = self.snapshots.get(rover)
        self.snapshots[rover] = snapshot
        valid = self.fresh(rover)
        old = self.positions.get(rover)
        if valid and (old is None or snapshot.position_timestamp > old[2]):
            point = (snapshot.latitude,snapshot.longitude)
            trail = self.trails.setdefault(rover,deque(maxlen=200))
            if old is not None and snapshot.position_timestamp-old[2] > 5:
                trail.clear()
            if not trail or trail[-1] != point:
                trail.append(point)
            self.positions[rover] = (*point,snapshot.position_timestamp)
            if self.follow_rover == rover:
                self._center = point
            elif self.auto_fit:
                shown=self.project(point)
                if old is None or not self.rect().adjusted(40,40,-100,-40).contains(shown.toPoint()):
                    self.fit_fleet()
        current = self.positions.get(rover)
        if (None if old is None else old[:2]) != (None if current is None else current[:2]) or was_fresh != self.fresh(rover) or (old_snapshot is not None and old_snapshot.heading != snapshot.heading):
            self.update()

    def fresh(self,rover,now=None):
        now = time.monotonic() if now is None else now
        s = self.snapshots.get(rover)
        return bool(s is not None and s.running and position_fresh(s,now)
            and s.last_heartbeat is not None and 0 <= now-s.last_heartbeat <= 5
            and all(type(v) in (int,float) and math.isfinite(v) for v in (s.latitude,s.longitude))
            and -85 <= s.latitude <= 85 and -180 <= s.longitude <= 180
            and not (abs(s.latitude) < 1e-7 and abs(s.longitude) < 1e-7)
            and (s.gps_timestamp is None or 0 <= now-s.gps_timestamp <= 5))

    def labels(self,now=None):
        now = time.monotonic() if now is None else now
        return {rover: f'Rover {rover}' + ('' if self.fresh(rover,now) else f' · stale {max(0,now-p[2]):.0f}s')
            for rover,p in self.positions.items()}

    def project(self,point):
        cx,cy = world_pixel(*self._center,self._zoom)
        x,y = world_pixel(*point,self._zoom)
        size = 256*2**self._zoom
        return QPointF(self.width()/2+(x-cx+size/2)%size-size/2,self.height()/2+y-cy)

    def _manual_view(self):
        super()._manual_view()
        self.follow_rover=None
        self.auto_fit=False

    def fit_fleet(self):
        self.cancel_pan()
        self.auto_fit=True
        points = [p[:2] for p in self.positions.values()]
        if not points:
            return
        # Circular longitude mean keeps vehicles near the date line together.
        lon = math.degrees(math.atan2(sum(math.sin(math.radians(p[1])) for p in points),
            sum(math.cos(math.radians(p[1])) for p in points)))
        self._center = (sum(p[0] for p in points)/len(points),lon)
        self.follow_rover = None
        for zoom in range(18,-1,-1):
            self._zoom = zoom
            if all(40 <= self.project(p).x() <= self.width()-100 and 40 <= self.project(p).y() <= self.height()-40 for p in points):
                break
        self.update()

    def forget(self, rover):
        """Remove only this roster entry's display state; never issue commands."""
        for values in (self.snapshots, self.positions, self.trails):
            values.pop(rover, None)
        if self.follow_rover == rover:
            self.follow_rover = None
        self.update()

    def _paint_overlays(self,painter):
        super()._paint_overlays(painter)
        if self._center is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        occupied=[]
        labels=self.labels()
        for rover,point in self.positions.items():
            color = QColor(self.COLORS[(rover-1)%len(self.COLORS)] if self.fresh(rover) else '#9ca3af')
            trail = self.trails.get(rover,())
            if len(trail)>1:
                path = QPainterPath(self.project(trail[0]))
                for p in list(trail)[1:]:
                    path.lineTo(self.project(p))
                painter.setPen(QPen(color,2));painter.drawPath(path)
            p = self.project(point[:2])
            painter.setBrush(color);painter.setPen(QPen(QColor('white'),2 if rover==self.selected_rover else 1))
            heading = self.snapshots[rover].heading
            if self.fresh(rover) and heading is not None and math.isfinite(heading) and 0 <= heading < 360:
                painter.save();painter.translate(p);painter.rotate(heading)
                marker = QPainterPath();marker.moveTo(0,-11);marker.lineTo(7,7)
                marker.lineTo(0,4);marker.lineTo(-7,7);marker.closeSubpath()
                painter.drawPath(marker);painter.restore()
            else:
                painter.drawEllipse(p,6,6)
            label = labels[rover]
            x,y = p.x()+10,p.y()-10
            width=painter.fontMetrics().horizontalAdvance(label)+4
            for step in range(40):
                offset=18*((step+1)//2)*(1 if step%2 else -1) if step else 0
                candidate=QRectF(x,y+offset-14,width,18)
                if not any(candidate.intersects(r) for r in occupied):
                    y+=offset;occupied.append(candidate);break
            if abs(y-(p.y()-10))>1:
                painter.setPen(QPen(color,1));painter.drawLine(p,QPointF(x,y))
            badge=QRectF(x-4,y-14,width+6,20)
            painter.setPen(QPen(color,1));painter.setBrush(QColor('#192534'))
            painter.drawRoundedRect(badge,4,4)
            painter.setPen(color);painter.drawText(QPointF(x,y),label)
        live = sum(self.fresh(rover) for rover in self.positions)
        painter.fillRect(QRectF(0,0,min(self.width(),300),28),QColor('#192534'))
        painter.setPen(QColor('#a4b2c4'))
        painter.drawText(8,18,f'{live} GPS live · {len(self.positions)-live} stale · Rover {self.selected_rover} plan')
