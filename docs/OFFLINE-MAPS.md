# Offline rover maps

PC TeleRC 0.1.3 supports local raster MBTiles and persistent online-tile caching. The Windows map uses Qt's native renderer; it does not require a web browser, MapLibre CDN, map style download or internet connection to display a local map.

## Open a map before going offline

1. Prepare a raster MBTiles file covering your operating area at the zoom levels you need. PNG, JPEG and WebP tiles, 256 or 512 pixels, are supported. Vector PBF/MVT MBTiles and Android MapLibre offline databases are different formats and cannot be opened here. No geographic map is bundled.
2. Open **Settings → Camera → Open offline map…** and select the `.mbtiles` file. The app remembers its location and automatically turns **Online map tiles** off. Keep the file at that location between launches; the application reads it without modifying it.
3. Drag the map to browse. Use +/− or the mouse wheel to zoom. Click **◎** to follow the rover again. A map's center/bounds are used for browsing before GPS is available; they never create a rover position, heartbeat or home point.
4. Use the **▁** button in the map's bottom bar to minimize it. A small **Map ▣** button stays in the lower-left corner; click to restore. This preference survives restart.
5. Missing local coverage is labeled **No saved tiles here**. Change zoom or load a map covering that area. The software does not download missing tiles from a local map's metadata.

## Cached online tiles

With no MBTiles file selected, online tiles viewed normally are cached on disk. Turn **Online map tiles** off to reuse them offline, including older cached tiles. A blank map means that zoom/location has no cached coverage. The last map view is saved on close and restored without implying a live GPS fix. Before first GPS or a map with center/bounds, the map displays a waiting state.

Click **Clear** to detach the local map without deleting the file. Re-enable **Online map tiles** to return to the online basemap. Imported maps take priority while selected.

The standard OpenStreetMap server is used only for visible online tiles; there is no bulk area downloader. Obtain planned offline coverage from a provider permitting offline use or generate raster MBTiles from your own GIS data. See https://operations.osmfoundation.org/policies/tiles/ and https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md.

## Position and control

The map displays real GPS from the locked ArduRover autopilot. It labels stale/unavailable GPS and does not estimate position from driving commands. A basemap can be browsed offline without GPS; a live rover marker still needs a fresh fix. Map controls do not arm or enable driving. Keyboard driving still stops on loss of its driving-area focus; re-enable manually after using settings or a file dialog.
