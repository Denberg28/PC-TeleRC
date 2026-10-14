#include <cassert>
#include <iostream>
#define TELERC_ROLE 3
#include "WiFiLink.h"
int main(){
 WiFi.modeFailures=1;setup();assert(!apReady&&wifiAttempts==1);
 clockMs=1999;loop();assert(wifiAttempts==1);
 WiFi.ipFailures=1;clockMs=2000;loop();assert(!apReady);
 WiFi.apFailures=1;clockMs=4000;loop();assert(!apReady);
 udp.beginFailures=1;clockMs=6000;loop();assert(apReady&&!udpReady);
 auto n=WiFi.apCalls;clockMs=8000;loop();assert(apReady&&udpReady&&WiFi.apCalls==n);
 WiFi.clients=0;clockMs+=3000;loop();assert(WiFi.apCalls==n);
 std::cout<<"PASS mode/IP/AP/UDP retries and idle AP preservation\n";
}
