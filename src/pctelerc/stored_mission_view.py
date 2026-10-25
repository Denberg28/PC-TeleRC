"""Modeless FC mission snapshot; no editing or vehicle-command access."""
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
    QHeaderView,QDialogButtonBox,QAbstractItemView)


class StoredMissionView(QDialog):
    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Stored FC mission · Rover {payload["rover"]}')
        self.setObjectName('StoredMissionView')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True)
        self.setModal(False)
        self.resize(620,390)
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,16);layout.setSpacing(12)
        rows=payload['rows']
        heading=QLabel(f'Rover {payload["rover"]} · '+('No stored mission' if not rows else f'{len(rows)} stored rows'))
        heading.setStyleSheet('font-size:16px; font-weight:600;')
        layout.addWidget(heading)
        stamp=datetime.fromtimestamp(payload['read_at']).strftime('%H:%M:%S')
        note=QLabel(f'Snapshot at {stamp} · Read-only\nPC draft unchanged. Upload and verify before arming or starting.')
        note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget(len(rows),3)
        self.table.setHorizontalHeaderLabels(['Row','Command','Location / values'])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        labels={16:'Waypoint',93:'Arrival hold',112:'Settling delay',178:'Speed',183:'Output'}
        for i,row in enumerate(rows):
            command=row['command']
            label=labels.get(command,f'CMD {command}')
            if row['seq']==0:label='Home / row 0' if command==16 else label
            detail=(f'{row["x"]/1e7:.7f}, {row["y"]/1e7:.7f}' if command==16
                else ' · '.join(f'p{j+1}: {value:g}' for j,value in enumerate(row['params'])))
            for col,text in enumerate((str(row['seq'])+(' •' if row.get('current') else ''),label,detail)):
                item=QTableWidgetItem(text);item.setToolTip(text)
                self.table.setItem(i,col,item)
        layout.addWidget(self.table,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close);layout.addWidget(buttons)
