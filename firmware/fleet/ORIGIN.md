This development family evolves Denberg28/PC-TeleRC's manual LoRa v1.0.1 node
reconnect fix and Mission 0.2.0rc1 foundation at v1.0.0 / commit
7b555bf1419587afb8932bbb3f145f31a11b5770.

The original firmware/mission and all existing manual profiles remain unchanged
in that repository. This source is added separately under firmware/fleet.
Protocol.h preserves the Mission Gate/parser behavior; its response buffer adds
8 bytes for the observed device fingerprint. TinyOled and test adapters originate
from that mission family. The new TF2 crypto/routing/runtime, ID-based network
provisioning, gateway/monitor, packaging and tests are this development line.

Build dependencies are not bundled: Arduino ESP32 3.3.2, RadioLib 7.2.1,
mbedTLS from the ESP32 SDK, pymavlink 2.4.49 and pyserial 3.5.
