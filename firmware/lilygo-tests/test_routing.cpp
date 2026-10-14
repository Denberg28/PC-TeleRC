#define main original_test_main
#include "test_wifi.cpp"
#undef main
int main(){
 setup();fcHeartbeat();
 udp.port=12345;receive(rc(1500,1500));assert(!safety.owned&&!linkLed.havePeer);
 udp.port=14550;udp.sender=IPAddress(10,0,0,2);receive(rc(1500,1500));assert(!safety.owned);
 udp.sender=IPAddress(192,168,4,2);text("TELERC_DISCOVER_V1");assert(peer==udp.sender&&!safety.owned);
 udp.sender=IPAddress(192,168,4,3);receive(rc(1500,1500));assert(!safety.owned);
 clockMs+=5000;fcHeartbeat();receive(rc(1500,1500));assert(safety.owned==3&&peer==udp.sender);
 auto oversized=std::vector<uint8_t>(1024,0);auto n=vehicle.frames.size();receive(oversized);assert(vehicle.frames.size()==n);
 receive(heartbeat(false));assert(vehicle.frames.back()==heartbeat(false));
 const auto at=safety.at[0];clockMs=at+500;receive(heartbeat(false));assert(!safety.owned); // GCS HB does not refresh axes
 clockMs=1250;fcHeartbeat();linkLed.received(clockMs);serviceLed();assert(pinLevels[37]==HIGH);
 clockMs=2749;serviceLed();assert(pinLevels[37]==HIGH);
 clockMs=2750;serviceLed();assert(pinLevels[37]==LOW);
 // Losing the Wi-Fi client discards any already queued drive packet.
 fcHeartbeat();receive(rc(1500,1500));udp.incoming=rc(1700,1600);WiFi.clients=0;loop();
 assert(udp.incoming.empty()&&!safety.owned&&peer==NO_PEER);
 WiFi.clients=1;loop();assert(!safety.owned);
 // Watchdog and LED freshness must remain valid when millis wraps.
 clockMs=UINT32_MAX-99;fcHeartbeat();receive(rc(1500,1500));
 const uint32_t last=safety.at[0];clockMs=uint32_t(last+500);loop();assert(!safety.owned);
 std::cout<<"PASS local endpoint/port lock, inactive peer handover, oversized datagram, heartbeat independent of command timeout, LED freshness, stale client queue purge and millis rollover\n";
}
