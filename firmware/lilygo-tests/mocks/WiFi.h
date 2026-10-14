#pragma once
#include "Arduino.h"
struct IPAddress {
 uint8_t parts[4];
 IPAddress(uint8_t a,uint8_t b,uint8_t c,uint8_t d):parts{a,b,c,d}{}
 uint8_t operator[](int i)const{return parts[i];}
 bool operator==(const IPAddress& b)const{return memcmp(parts,b.parts,4)==0;}
 bool operator!=(const IPAddress& b)const{return !(*this==b);}
 String toString()const{return "192.168.4.2";}
};
constexpr int WIFI_OFF=0,WIFI_AP=1;
struct WiFiMock{
 int active=0;
 int modeFailures=0,ipFailures=0,apFailures=0,apCalls=0,clients=1;
 int lastChannel=0,lastHidden=-1;
 bool mode(int m){if(m==WIFI_AP && modeFailures>0){--modeFailures;return false;}active=m;return true;}
 int getMode(){return active;}
 bool softAPConfig(IPAddress,IPAddress,IPAddress){if(ipFailures>0){--ipFailures;return false;}return true;}
 bool softAP(const char*,const char*,int channel,int hidden,int){
  ++apCalls;lastChannel=channel;lastHidden=hidden;
  if(apFailures>0){--apFailures;return false;}return true;
 }
 int softAPgetStationNum(){return clients;}
 IPAddress softAPIP(){return IPAddress(192,168,4,1);}
};
inline WiFiMock WiFi;
