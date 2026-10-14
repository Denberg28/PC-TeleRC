#include <cassert>
#include <iostream>
#include "Runtime.h"
void tick(uint32_t ms,bool down=false){testMs=ms;pins[0]=down?LOW:HIGH;runtime::loop();}
void active(){
 lora::pollAt=testMs; // no RF scheduling in this display/ownership fixture
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE){wifi::haveFc=true;wifi::fcAt=testMs;wifi::safety.ready=true;wifi::safety.owned=3;wifi::safety.at[0]=wifi::safety.at[1]=testMs;return;}
#endif
 if(TELERC_ROLE==3){lora::haveFc=true;lora::fcAt=testMs;lora::safety.ready=true;lora::safety.owned=3;lora::safety.at[0]=lora::safety.at[1]=testMs;}
}
void checkActive(){
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE){assert(wifi::safety.owned==3);return;}
#endif
 if(TELERC_ROLE==3)assert(lora::safety.owned==3);
}
int main(){
 lora::cfg.khz=915000;memset(lora::cfg.key,1,32);runtime::setup();
 const uint32_t start=runtime::screenAt;
 testMs=start+29999;active();tick(testMs);assert(!runtime::oled.asleep);checkActive();
 testMs=start+30000;active();tick(testMs);assert(runtime::oled.asleep&&!runtime::menu);checkActive();
 assert((Wire.transactions.back()==std::vector<uint8_t>{0,0xae}));
 size_t transactions=Wire.transactions.size();
 for(unsigned i=1;i<=50;++i){testMs=start+30000+i;active();tick(testMs);checkActive();}
 assert(Wire.transactions.size()==transactions); // asleep = no display bus traffic
 tick(start+30100,true);testMs=start+30130;active();tick(testMs,true);
 assert(!runtime::oled.asleep&&runtime::wakeGesture&&!runtime::menu);checkActive();
 // Even a long first press wakes only; it cannot stop an active session.
 testMs=start+31200;active();tick(testMs,true);assert(!runtime::menu);checkActive();
 testMs=start+31210;active();tick(testMs,false);testMs=start+31240;active();tick(testMs,false);
 assert(!runtime::wakeGesture&&!runtime::menu);checkActive();
 testMs=start+31300;active();tick(testMs,true);testMs=start+31330;active();tick(testMs,true);
 testMs=start+32330;active();tick(testMs,true);assert(runtime::menu); // separate intentional hold
#if TELERC_ROLE==3
 if(runtime::mode==runtime::WIFI_MODE)assert(!wifi::safety.owned);else assert(!lora::safety.owned);
#endif
 // Unsigned timeout comparison also works over millis wrap.
 runtime::menu=false;runtime::button={};runtime::oled.setAwake(true);runtime::screenAt=0xfffffff0;
 testMs=uint32_t(runtime::screenAt+29999);active();tick(testMs);assert(!runtime::oled.asleep);
 testMs=uint32_t(runtime::screenAt+30000);active();tick(testMs);assert(runtime::oled.asleep);checkActive();
 std::cout<<"Role "<<TELERC_ROLE<<": OLED off at 30 s, bus idle, BOOT wake gesture consumed, active control preserved, second hold enters setup, timer rollover passed\n";
}
