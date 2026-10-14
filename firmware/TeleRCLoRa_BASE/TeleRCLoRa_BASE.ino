// User settings: edit identically on BASE, ROVER and every NODE, then upload.
// Empty password uses saved pairing. Non-empty password overrides saved pairing.
#define TELERC_LORA_PASSWORD ""       // exactly 8 visible ASCII characters; no spaces
#define TELERC_LORA_FREQUENCY_KHZ 915000 // set for your hardware and permitted band
#define TELERC_LORA_POWER_DBM 2
#define TELERC_RELAY_COUNT 0          // 0=direct, 1=one NODE, 2=two NODEs; match ALL boards
#define TELERC_TRANSPORT_WIFI 0 // ROVER initial default: 0 LoRa, 1 Wi-Fi; saved BOOT choice wins
#define TELERC_NODE_INDEX 1           // NODE only: 1 nearest BASE, 2 nearest ROVER
#define TELERC_ROLE 1
#include "Runtime.h"
void setup(){runtime::setup();}
void loop(){runtime::loop();}
