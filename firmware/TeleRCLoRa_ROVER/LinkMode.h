#pragma once
// 1 = LilyGO Wi-Fi AP (default); 0 = existing SX1262 LoRa direct pair.
// Select while motor power is disconnected, then upload/restart the ROVER.
#ifndef TELERC_TRANSPORT_WIFI
#define TELERC_TRANSPORT_WIFI 1
#endif
#if TELERC_TRANSPORT_WIFI != 0 && TELERC_TRANSPORT_WIFI != 1
#error "TELERC_TRANSPORT_WIFI must be 0 (LoRa) or 1 (Wi-Fi)"
#endif
