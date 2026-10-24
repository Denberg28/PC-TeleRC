#pragma once
#include <vector>
#include <cstring>
#define RADIOLIB_ERR_NONE 0
#define RADIOLIB_SX126X_IRQ_TX_DONE 1
struct Module {Module(int,int,int,int){}};
struct SX1262 {
 std::vector<uint8_t>sent,incoming;bool fail=false;void(*handler)()=nullptr;
 SX1262(Module*){}
 uint32_t getIrqFlags(){return fail?0:1;}
 int begin(float,float,int,int,int,int,int,float){return 0;}
 int setRxBoostedGainMode(bool,bool){return 0;}
 void setDio1Action(void(*p)()){handler=p;}
 int startReceive(){return fail?-1:0;}
 int standby(){return 0;}
 int finishTransmit(){return fail?-1:0;}
 uint32_t getTimeOnAir(size_t n){return n*1000;}
 size_t getPacketLength(){return incoming.size();}
 int readData(uint8_t*p,size_t n){memcpy(p,incoming.data(),n);incoming.clear();return 0;}
 int startTransmit(uint8_t*p,size_t n){if(fail)return -1;sent.assign(p,p+n);return 0;}
};
