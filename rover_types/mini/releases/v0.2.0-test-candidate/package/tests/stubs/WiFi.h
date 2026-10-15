#pragma once
#include <stdint.h>
#include <array>
#define WIFI_AP 2
class IPAddress {
  std::array<uint8_t,4> bytes;
public:
  IPAddress(uint8_t a=0,uint8_t b=0,uint8_t c=0,uint8_t d=0):bytes{a,b,c,d} {}
  uint8_t operator[](int i) const { return bytes[i]; }
  bool operator==(const IPAddress &o) const { return bytes==o.bytes; }
  bool operator!=(const IPAddress &o) const { return !(*this==o); }
};
struct FakeWiFi {
  unsigned stations=1;
  bool startupOK=true;
  void persistent(bool) {}
  void mode(int) {}
  void setSleep(bool) {}
  bool softAPConfig(IPAddress,IPAddress,IPAddress) { return startupOK; }
  bool softAP(const char *,const char *,int,int,int) { return true; }
  unsigned softAPgetStationNum() { return stations; }
};
inline FakeWiFi WiFi;
