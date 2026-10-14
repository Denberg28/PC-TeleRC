# Third-party components

- PySide6 / Qt 6.11.2: Qt GUI, networking and multimedia; LGPL/GPL/commercial licensing as distributed by The Qt Company. See https://doc.qt.io/qt-6/licensing.html and https://doc.qt.io/qtforpython-6/licenses.html.
- FFmpeg multimedia libraries distributed with Qt: codec/network video backend; licensing depends on the supplied library configuration. See https://www.ffmpeg.org/legal.html. The Windows package retains the Qt/FFmpeg runtime supplied by the pinned PySide6 distribution.
- pymavlink 2.4.50, pygame-ce 2.5.8 and pyserial 3.5 retain their upstream licensing and notices distributed with their packages.
- Map data: © OpenStreetMap contributors, ODbL. https://www.openstreetmap.org/copyright. Public raster tiles are subject to https://operations.osmfoundation.org/policies/tiles/.
- TeleRC logo: reused from this user's TeleRC repository asset `app/src/main/res/drawable-nodpi/ic_telerc.png`, blob `f3b2797cbe78d27404a25308b7e8b65f560b19fe`. The Windows ICO is a size conversion of that original logo.
- `test-pattern.mp4` is a synthetic two-second video generated locally from FFmpeg's test pattern solely for source/frozen-package media validation. It is not a camera recording or live feed.

The application layout takes general inspiration from camera-oriented flight-controller interfaces; it does not include DJI artwork, branding or software.
