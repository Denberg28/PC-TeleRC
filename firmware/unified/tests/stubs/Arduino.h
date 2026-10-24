#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <deque>
#include <vector>
#define IRAM_ATTR
#define INPUT_PULLUP 1
#define OUTPUT 2
#define LOW 0
#define HIGH 1
#define SERIAL_8N1 0
inline uint32_t clockMs=0;
inline uint32_t millis(){return clockMs;}
inline void delay(uint32_t n){clockMs+=n;}
inline void pinMode(int,int){}
inline int digitalRead(int pin){return pin==33?LOW:HIGH;}
inline void digitalWrite(int,int){}
struct HardwareSerial {
 std::deque<uint8_t>rx;std::vector<uint8_t>tx;int room=4096;bool enabled=true;
 HardwareSerial(int=0){}
 void begin(int,int=0,int=0,int=0){}
 void setTxTimeoutMs(int){}
 void setRxBufferSize(int){}
 void setTxBufferSize(int){}
 int available(){return rx.size();}
 int availableForWrite(){return room;}
 int read(){int b=rx.front();rx.pop_front();return b;}
 size_t write(const uint8_t*p,size_t n){if(int(n)>room)return 0;tx.insert(tx.end(),p,p+n);return n;}
 explicit operator bool()const{return enabled;}
};
inline HardwareSerial Serial;
