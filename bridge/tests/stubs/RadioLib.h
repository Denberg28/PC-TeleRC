#pragma once
#include "Arduino.h"
#define RADIOLIB_ERR_NONE 0
#define RADIOLIB_CHANNEL_FREE -15
#define RADIOLIB_LORA_DETECTED -702
struct Module {Module(int,int,int,int){}};
struct RadioMock {
 std::vector<uint8_t> rx;std::vector<std::vector<uint8_t>> tx;int result=0,receiveResult=0,scanResult=RADIOLIB_CHANNEL_FREE;
 RadioMock(Module*){}
 int startReceive(){return receiveResult;}int standby(){rx.clear();return 0;}
 size_t getPacketLength(){return rx.size();}
 int readData(uint8_t*p,size_t n){if(n>rx.size())return -1;memcpy(p,rx.data(),n);rx.clear();return result;}
 float getRSSI(){return -70;}int startChannelScan(){return result;}int getChannelScanResult(){return scanResult;}int finishTransmit(){return 0;}int startTransmit(uint8_t*p,size_t n){tx.emplace_back(p,p+n);return result;}
 int transmit(uint8_t*p,size_t n){tx.emplace_back(p,p+n);return result;}
};
struct SX1262:RadioMock {
 using RadioMock::RadioMock;
 int begin(float,float,uint8_t,uint8_t,uint8_t,int8_t,uint16_t,float=1.6,bool=false){return 0;}
 int setRxBoostedGainMode(bool,bool){return 0;}
 uint32_t getTimeOnAir(size_t n){return 256*(81+20*((8*n+16+27)/28))/4;}
 void setDio1Action(void(*)()){}
};
struct SX1276:RadioMock {
 using RadioMock::RadioMock;
 int begin(float,float,uint8_t,uint8_t,uint8_t,int8_t,uint16_t,uint8_t=0){return 0;}
 void setDio0Action(void(*)(),uint32_t){}
};
