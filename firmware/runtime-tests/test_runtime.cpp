#include <cassert>
#include <iostream>
#ifndef TELERC_ROLE
#define TELERC_ROLE 3
#endif
#include "Runtime.h"
void tick(uint32_t ms,bool pressed){testMs=ms;pins[0]=pressed?LOW:HIGH;runtime::loop();}
int main(){
 // Blank NVS must allow BOOT setup without touching an uninitialized SPI radio.
 runtime::setup();assert(!lora::radioOK);
 runtime::pause();assert(runtime::menu&&lora::radio.standbyCalls==0);
 runtime::menu=false; // simulate the next startup with a provisioned key below

#if TELERC_ROLE==1
 Preferences::storage["telerc-ui/mode"]={1}; // BASE must ignore unsupported Wi-Fi data mode
#endif
 lora::cfg.khz=915000;memset(lora::cfg.key,1,32);
 runtime::setup();
 assert(Wire.timeout==1&&Wire.maxBytes<=32);
 assert(runtime::mode==(TELERC_ROLE==3?uint8_t(TELERC_TRANSPORT_WIFI):runtime::LORA_MODE));
 tick(1000,true);tick(1030,true);tick(2029,true);assert(!runtime::menu);
 // Acquire immediately before entering setup, with the UART blocked.
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE){wifi::safety.owned=3;wifi::vehicle.capacity=0;}
 else {lora::safety.owned=3;lora::vehicle.capacity=0;}
#else
 lora::stopPending=true;lora::vehicle.capacity=0;
#endif
 tick(2030,true);assert(runtime::menu&&!runtime::restarting); // HOLD must not also select
 tick(2035,false);tick(2065,false);assert(!runtime::restarting);
 assert(!lora::radioOK&&runtime::pendingStop());
 assert(!runtime::restart(runtime::LORA_MODE));
 // Backpressure blocks a transport change rather than abandoning a stop frame.
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE){
  assert(!wifi::safety.owned&&!wifi::udpReady&&wifi::vehicle.tx.empty());
  wifi::vehicle.capacity=1024;
 }else {assert(!lora::safety.owned&&lora::vehicle.tx.empty());lora::vehicle.capacity=1024;}
#else
 lora::vehicle.capacity=1024;
#endif
 tick(2200,false);assert(!runtime::pendingStop());
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE)assert(wifi::vehicle.tx.size()==52);
 else assert(lora::vehicle.tx.size()==52);
#endif
 Preferences::fail=true;assert(!runtime::restart(runtime::LORA_MODE)&&!runtime::restarting);Preferences::fail=false;
 runtime::startPortal();assert(runtime::portal&&runtime::server.running);
 runtime::server.call("/",HTTP_GET);assert(runtime::server.status==200);
 assert(runtime::server.body.find("exactly 8")!=std::string::npos);
 runtime::server.arguments={{"csrf","wrong"},{"mode","0"},{"mhz","915.000"},{"power","2"},{"password","Ab12Cd34"}};
 runtime::server.call("/save",HTTP_POST);assert(runtime::server.status==409);
 runtime::server.arguments["csrf"]=runtime::csrf;
 runtime::server.arguments["password"]="short";
 runtime::server.call("/save",HTTP_POST);assert(runtime::server.status==400&&!runtime::restarting);
 runtime::server.arguments["password"]="Ab12Cd34";
 runtime::server.call("/save",HTTP_POST);assert(runtime::server.status==200&&runtime::restarting);
 assert(lora::cfg.khz==915000&&lora::validConfig(lora::cfg));
 uint8_t expected[32];assert(telerc::passwordKey("Ab12Cd34",8,expected));assert(!memcmp(expected,lora::cfg.key,32));
 uint8_t vector[32];const char*hex="1bd10955bf293a2ec597c50b47cc23f28f560b9f3c3c0eaf214d61b545849fba";
 for(unsigned i=0;i<32;++i){char pair[3]={hex[i*2],hex[i*2+1],0};vector[i]=uint8_t(strtoul(pair,nullptr,16));}
 assert(!memcmp(expected,vector,32));
 assert(!telerc::passwordKey("1234 678",8,expected)&&!telerc::passwordKey("1234567",7,expected));
 auto&saved=Preferences::storage["telerc-lora2/config"];
 assert(saved.size()==sizeof(lora::Config));
 assert(std::search(saved.begin(),saved.end(),(const uint8_t*)"Ab12Cd34",(const uint8_t*)"Ab12Cd34"+8)==saved.end());
 assert(runtime::server.body.find("Ab12Cd34")==std::string::npos);
 tick(runtime::pausedAt+15999,false);assert(!ESP.restarted);
 tick(runtime::pausedAt+16000,false);assert(ESP.restarted);
 assert(Preferences::storage["telerc-ui/mode"]==std::vector<uint8_t>{0});
 // Saved transport overrides the default build seed on the next boot.
 runtime::setup();assert(runtime::mode==runtime::LORA_MODE&&lora::cfg.khz==915000&&lora::radioOK);
 telerc::BootButton bounce;
 assert(bounce.update(true,0xfffffff0)==telerc::Press::NONE);
 assert(bounce.update(false,0xfffffff5)==telerc::Press::NONE);
 assert(bounce.update(true,0xfffffffa)==telerc::Press::NONE);
 assert(bounce.update(true,24)==telerc::Press::NONE);
 assert(bounce.update(true,1023)==telerc::Press::NONE);
 assert(bounce.update(true,1024)==telerc::Press::HOLD);
 assert(bounce.update(false,1025)==telerc::Press::NONE);
 assert(bounce.update(false,1055)==telerc::Press::NONE);
 // OLED faults never gate link state or force an uncontrolled display retry.
 Wire.failed=true;runtime::oled.ready=true;runtime::paint();runtime::oled.step();assert(!runtime::oled.ready);
 uint32_t freq=0;assert(telerc::frequencyKHz("433.250",freq)&&freq==433250);
 assert(!telerc::frequencyKHz("nan",freq)&&!telerc::frequencyKHz("915.",freq)&&!telerc::frequencyKHz("915.0000",freq));
 std::cout<<"Runtime role "<<TELERC_ROLE<<": BOOT debounce/hold, no double-select, pending stop, physical setup, CSRF, 8-character pairing, secret-free storage/reply, mode save, safe restart delay and OLED failure passed\n";
}
