#pragma once
#include "WiFi.h"
struct WiFiUDP {
 std::vector<uint8_t> incoming;
 std::vector<std::vector<uint8_t>> sent;
 IPAddress sender{192,168,4,2};
 uint16_t port=14550;
 int beginFailures=0,beginCalls=0;
 bool begin(uint16_t){++beginCalls;if(beginFailures>0){--beginFailures;return false;}return true;}
 void stop(){incoming.clear();}
 int parsePacket(){return int(incoming.size());}
 IPAddress remoteIP(){return sender;}
 uint16_t remotePort(){return port;}
 int read(uint8_t* p,size_t n){n=std::min(n,incoming.size());std::copy_n(incoming.begin(),n,p);incoming.erase(incoming.begin(),incoming.begin()+n);return int(n);}
 int read(){incoming.erase(incoming.begin());return 0;}
 int available(){return int(incoming.size());}
 bool beginPacket(IPAddress,uint16_t){return true;}
 size_t write(const uint8_t* p,size_t n){sent.emplace_back(p,p+n);return n;}
 bool endPacket(){return true;}
};
