#pragma once
#include "WiFi.h"
#include <vector>
#include <deque>
#include <algorithm>
class WiFiUDP {
public:
  struct Packet { IPAddress ip; uint16_t port; std::vector<uint8_t> data; };
  std::deque<Packet> incoming;
  std::vector<Packet> outgoing;
  Packet active{}, tx{};
  size_t cursor=0;
  bool begin(uint16_t) { return true; }
  int parsePacket() {
    if(incoming.empty()) return 0;
    active=incoming.front(); incoming.pop_front(); cursor=0;
    return active.data.size();
  }
  IPAddress remoteIP() { return active.ip; }
  uint16_t remotePort() { return active.port; }
  int read(uint8_t *data,size_t size) {
    size_t n=std::min(size,active.data.size()-cursor);
    std::copy_n(active.data.data()+cursor,n,data); cursor+=n; return n;
  }
  int available() { return active.data.size()-cursor; }
  int read() { return available() ? active.data[cursor++] : -1; }
  bool beginPacket(IPAddress ip,uint16_t port) { tx={ip,port,{}}; return true; }
  size_t write(const uint8_t *data,size_t size) { tx.data.insert(tx.data.end(),data,data+size); return size; }
  bool endPacket() { outgoing.push_back(tx); return true; }
};
