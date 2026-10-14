#pragma once
#include <stdint.h>
#include <stddef.h>
#ifndef TELERC_LORA_PASSWORD
#define TELERC_LORA_PASSWORD ""
#endif
#ifndef TELERC_LORA_FREQUENCY_KHZ
#define TELERC_LORA_FREQUENCY_KHZ 915000
#endif
#ifndef TELERC_LORA_POWER_DBM
#define TELERC_LORA_POWER_DBM 2
#endif
#ifndef TELERC_RELAY_COUNT
#define TELERC_RELAY_COUNT 0
#endif
#ifndef TELERC_NODE_INDEX
#define TELERC_NODE_INDEX 1
#endif
namespace settings {
inline constexpr char PASSWORD[]=TELERC_LORA_PASSWORD;
constexpr bool COMPILED_PAIRING=sizeof(PASSWORD)>1;
constexpr uint8_t RELAYS=TELERC_RELAY_COUNT,LEGS=RELAYS+1,NODE_INDEX=TELERC_NODE_INDEX;
constexpr uint16_t nodeId(uint8_t index){return uint16_t(2+index);}
constexpr uint16_t SELF=TELERC_ROLE==1?1:TELERC_ROLE==3?2:nodeId(NODE_INDEX);
constexpr bool visiblePassword(){
 if(sizeof(PASSWORD)!=1&&sizeof(PASSWORD)!=9)return false;
 for(size_t i=0;i+1<sizeof(PASSWORD);++i)if(uint8_t(PASSWORD[i])<33||uint8_t(PASSWORD[i])>126)return false;
 return true;
}
static_assert(visiblePassword(),"Set an empty password for saved pairing, or exactly 8 visible ASCII characters (no spaces)");
static_assert(TELERC_RELAY_COUNT>=0&&TELERC_RELAY_COUNT<=2,"Use 0, 1 or 2 relay nodes on every participant");
static_assert(TELERC_ROLE!=2||(TELERC_NODE_INDEX>=1&&TELERC_NODE_INDEX<=TELERC_RELAY_COUNT),"NODE_INDEX must be 1..RELAY_COUNT; index 1 is nearest BASE");
static_assert(!COMPILED_PAIRING||((TELERC_LORA_FREQUENCY_KHZ>=400250&&TELERC_LORA_FREQUENCY_KHZ<=519750)||(TELERC_LORA_FREQUENCY_KHZ>=830250&&TELERC_LORA_FREQUENCY_KHZ<=944750)),"Choose a valid frequency for the SX1262 hardware");
static_assert(TELERC_LORA_POWER_DBM>=2&&TELERC_LORA_POWER_DBM<=17,"Power must be 2..17 dBm");
}
