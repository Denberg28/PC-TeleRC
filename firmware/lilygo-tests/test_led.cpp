#include <cassert>
#include <cstdint>
#include <iostream>
#include "LinkLed.h"
int main(){
 telerc::LinkLed led;
 assert(led.on(0,true));
 assert(led.on(249,true));
 assert(!led.on(250,true));
 assert(!led.on(499,true));
 assert(led.on(500,true));
 led.received(1250);
 assert(led.on(1250,true)); // search would be OFF here
 assert(led.on(1749,true));
 assert(!led.on(1750,true)); // exact 500 ms expiry, OFF blink phase
 led.received(1800);
 assert(led.on(1800,true)); // recovery
 assert(!led.on(1800,false)); // radio failure/maintenance overrides freshness
 assert(led.on(1800,true));
 telerc::LinkLed reboot;
 assert(!reboot.on(250,true)); // old link does not survive reboot
 telerc::LinkLed wrap;
 wrap.received(UINT32_MAX-99);
 assert(wrap.on(100,true));
 assert(wrap.on(399,true));
 assert(!wrap.on(400,true)); // 500 ms age across millis rollover
 std::cout << "PASS: LED search, valid receipt, 500 ms expiry, recovery, radio disable, reboot and rollover\n";
}
