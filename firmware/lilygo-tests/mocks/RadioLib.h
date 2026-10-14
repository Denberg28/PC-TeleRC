#pragma once
#include <cstddef>
#include <cstdint>
constexpr int RADIOLIB_ERR_NONE=0,RADIOLIB_LORA_DETECTED=1,RADIOLIB_CHANNEL_FREE=2;
struct Module{Module(int,int,int,int){}};
struct SX1262{
 SX1262(Module*){}
 int startReceive(){return 0;}
 void standby(){}
 int startChannelScan(){return 0;}
 int getChannelScanResult(){return RADIOLIB_CHANNEL_FREE;}
 uint32_t getTimeOnAir(size_t){return 10000;}
 int startTransmit(const uint8_t*,size_t){return 0;}
 void finishTransmit(){}
 size_t getPacketLength(){return 0;}
 int readData(uint8_t*,size_t){return 0;}
 int begin(float,float,int,int,int,int,int,float){return 0;}
 int setRxBoostedGainMode(bool,bool){return 0;}
 void setDio1Action(void(*)()){}
};
