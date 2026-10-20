# Actual board qualification recipe

The final build uses the bundled `lilygo-sx1262-4mb.json` board definition: standard 4 MB LilyGO T3-S3, SX1262 manufacturer pin variant, native hardware USB CDC and no PSRAM. It is derived from the installed manufacturer profile.

Tool versions: PlatformIO Core 6.1.18; pioarduino platform 55.03.32; Espressif Arduino core 3.3.2 / SDK IDF 5.5.1; Xtensa ESP GCC 14.2.0+20250730; RadioLib 7.2.1. The dependency installer needed its local Python dependencies and pinned esptool source path configured before the clean build. No sketch or RadioLib/API/SDK implementation was modified to skip a test or obtain a link result.

To reproduce, create a PlatformIO project with the included board JSON under `boards/telerc-lilygo-sx1262.json`; copy canonical firmware headers to `src/`, and use a generated private profile Config.h. Add `src/main.cpp` containing `#include "Runtime.h"`. The included qualification INI illustrates BASE/ROVER/NODE1/NODE2 role compilation. Its ROLE/NODE_INDEX flags require the corresponding Config.h definitions to be guarded with #ifndef, or compile each generated role in its own project and remove those flags. Use RELAY_COUNT=2 for both node indices. BASE holds the generated fleet key table, ROVER its own key, NODE only the routing key and a dummy zero rover-key entry. Never use the public keyless Config.h to test actual RF delivery.

The normal Arduino IDE / tools/compile_profiles.py route needs no custom board JSON and compiles generated role folders directly with the manufacturer LilyGo T3-S3 Radio-SX1262 profile. No precompiled operational firmware or test private keys are distributed.
