#include <cassert>
#include <iostream>
#ifndef TEST_BASE
#define TELERC_TRANSPORT_WIFI 0
#define TELERC_ROLE 3
#include "Link.h"
#else
#define TELERC_ROLE 1
#include "Link.h"
#endif
int main(){
 setup();assert(maintenance&&!radioOK); // unprovisioned -> no RF/ownership
 clockMs=250;loop();assert(pinLevels[37]==LOW);
 clockMs=500;loop();assert(pinLevels[37]==HIGH);
 assert(!safety.owned);
 std::cout<<"PASS LoRa role "<<TELERC_ROLE<<" host compilation, unconfigured maintenance and search LED\n";
}
