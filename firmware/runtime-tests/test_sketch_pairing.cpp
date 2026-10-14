#include <cassert>
#include <iostream>
#include "Runtime.h"
int main(){
 assert(settings::COMPILED_PAIRING);
 lora::Config old;old.khz=433250;memset(old.key,0x55,32);
 Preferences::storage["telerc-lora2/config"].assign((uint8_t*)&old,(uint8_t*)&old+sizeof(old));
 runtime::setup();assert(lora::sketchPairing&&lora::cfg.khz==915000&&lora::cfg.power==2);
 uint8_t expected[32];assert(telerc::passwordKey("Ab12Cd34",8,expected));assert(!memcmp(expected,lora::cfg.key,32));
 runtime::pause();runtime::startPortal();assert(!runtime::portal);
 std::string request="TELERC_LORA_SET_V1,433250,2,"+std::string(64,'1');
 lora::provision((const uint8_t*)request.data(),request.size());
 while(lora::usbCount)lora::serviceUsbTx();
 telerc::UartParser parser;bool locked=false;
 for(uint8_t b:Serial.tx)if(parser.feed(b,testMs))locked=locked||telerc::textEquals(parser.data+4,parser.length(),"TELERC_LORA_RESULT_V1,SKETCH_PAIRING_LOCKED");
 assert(locked&&lora::cfg.khz==915000&&!memcmp(expected,lora::cfg.key,32));
 assert(Preferences::storage["telerc-lora2/config"]==std::vector<uint8_t>((uint8_t*)&old,(uint8_t*)&old+sizeof(old)));
 assert(!lora::safety.owned&&lora::vehicle.tx.empty());
 if(TELERC_ROLE==2)assert(runtime::mode==runtime::LORA_MODE);
 std::cout<<"Role "<<TELERC_ROLE<<": sketch password/frequency overrides NVS; web/USB cannot replace it; no auto control passed\n";
}
