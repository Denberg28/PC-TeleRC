#pragma once
#include "WiFi.h"
struct WiFiUDP {std::vector<uint8_t> rx;size_t cursor=0;IPAddress peer{192,168,4,2};int parsePacket(){return rx.size();}IPAddress remoteIP(){return peer;}uint16_t remotePort(){return 14550;}int read(uint8_t*p,size_t n){n=std::min(n,rx.size()-cursor);memcpy(p,rx.data()+cursor,n);cursor+=n;return n;}int read(){return cursor<rx.size()?rx[cursor++]:-1;}int available(){return rx.size()-cursor;}bool begin(int){return true;}bool beginPacket(IPAddress,int){return true;}size_t write(const uint8_t*,size_t n){return n;}bool endPacket(){return true;}};
