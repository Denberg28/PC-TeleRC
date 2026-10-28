"""Reproduce the PNG and multi-resolution Windows ICO from the native SVG."""
from pathlib import Path
import os
import struct

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QBuffer,QIODevice
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT=Path(__file__).resolve().parents[1]/'src/pctelerc/assets'


def build():
    app=QApplication.instance() or QApplication([])
    renderer=QSvgRenderer(str(ROOT/'telerc.svg'))
    if not renderer.isValid():raise RuntimeError('Invalid rover icon SVG')
    frames=[]
    for size in (16,24,32,48,64,128,256,512):
        image=QImage(size,size,QImage.Format.Format_ARGB32)
        image.fill(0)
        painter=QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter);painter.end()
        buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer,'PNG'):raise RuntimeError('PNG icon render failed')
        if size==512:
            (ROOT/'telerc.png').write_bytes(bytes(buffer.data()))
        else:
            frames.append((size,bytes(buffer.data())))
    offset=6+16*len(frames)
    entries=[]
    for size,data in frames:
        entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset))
        offset+=len(data)
    (ROOT/'telerc.ico').write_bytes(struct.pack('<HHH',0,1,len(frames))+b''.join(entries)+b''.join(data for _,data in frames))
    print('Rendered rover PNG and seven Windows icon resolutions')


if __name__=='__main__':build()
