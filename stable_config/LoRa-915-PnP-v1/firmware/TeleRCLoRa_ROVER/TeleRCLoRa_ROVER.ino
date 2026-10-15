// Direct LoRa preset pnp915-1: upload BASE and ROVER from this package together.
// Empty password uses saved pairing. Non-empty password overrides saved pairing.
#define TELERC_LORA_PASSWORD "telerc123"       // 9-character preset; accepts 8-32 visible ASCII characters
#define TELERC_LORA_FREQUENCY_KHZ 915000 // set for your hardware and permitted band
#define TELERC_LORA_POWER_DBM 2
#define TELERC_RELAY_COUNT 0          // 0=direct, 1=one NODE, 2=two NODEs; match ALL boards
#define TELERC_TRANSPORT_WIFI 0 // ROVER initial default: 0 LoRa, 1 Wi-Fi; saved BOOT choice wins
#define TELERC_NODE_INDEX 1           // NODE only: 1 nearest BASE, 2 nearest ROVER
#define TELERC_ROLE 3
#include "Runtime.h"
// On the first installation of this preset, replace a saved Wi-Fi selection.
// Subsequent boots retain deliberate BOOT-menu transport changes.
void setup(){
#if TELERC_ROLE == 3
 Preferences p;
 if(p.begin("telerc-ui",false)){
  if(p.getUChar("pnp915v1",0)!=1){
   if(p.putUChar("mode",0)==1)p.putUChar("pnp915v1",1);
  }
  p.end();
 }
#endif
 runtime::setup();
}
void loop(){runtime::loop();}
