#pragma once
#include "Arduino.h"
struct WireMock {
 bool failed=false;size_t bytes=0,maxBytes=0;uint16_t timeout=0;
 void begin(int,int){}void setClock(int){}void setTimeOut(uint16_t t){timeout=t;}
 void beginTransmission(int){bytes=0;}
 size_t write(uint8_t){++bytes;return 1;}
 size_t write(const uint8_t*,size_t n){bytes+=n;return n;}
 int endTransmission(){maxBytes=std::max(maxBytes,bytes);return failed?1:0;}
};
inline WireMock Wire;
