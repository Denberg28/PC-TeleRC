#pragma once
#include "Arduino.h"
struct WireMock {
 std::vector<std::vector<uint8_t>> transactions;std::vector<uint8_t> current;
 bool failed=false;size_t bytes=0,maxBytes=0;uint16_t timeout=0;
 void begin(int,int){}void setClock(int){}void setTimeOut(uint16_t t){timeout=t;}
 void beginTransmission(int){bytes=0;current.clear();}
 size_t write(uint8_t b){++bytes;current.push_back(b);return 1;}
 size_t write(const uint8_t*p,size_t n){bytes+=n;current.insert(current.end(),p,p+n);return n;}
 int endTransmission(){transactions.push_back(current);maxBytes=std::max(maxBytes,bytes);return failed?1:0;}
};
inline WireMock Wire;
