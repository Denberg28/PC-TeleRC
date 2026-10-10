#pragma once
#include "Arduino.h"
#define WIFI_AP 1
struct IPAddress {uint8_t bytes[4];IPAddress(int a=0,int b=0,int c=0,int d=0):bytes{uint8_t(a),uint8_t(b),uint8_t(c),uint8_t(d)}{}uint8_t operator[](int i)const{return bytes[i];}bool operator==(const IPAddress&o)const{return memcmp(bytes,o.bytes,4)==0;}bool operator!=(const IPAddress&o)const{return !(*this==o);}String toString()const{return "192.168.4.2";}};
struct WifiMock {void persistent(bool){}void mode(int){}void setSleep(bool){}bool softAPConfig(IPAddress,IPAddress,IPAddress){return true;}bool softAP(const char*,const char*,int=1,bool=false,int=4){return true;}int softAPgetStationNum(){return 1;}IPAddress softAPIP(){return {192,168,4,1};}};
inline WifiMock WiFi;
