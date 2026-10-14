#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <algorithm>
#include <array>
#include "esp_arduino_version.h"
using std::max;
#define IRAM_ATTR
#define F(x) x
#define HEX 16
#define INPUT_PULLUP 4
#define LOW 0
#define HIGH 1
#define INPUT_PULLDOWN 0
#define OUTPUT 1
#define CHANGE 2
#define RISING 3
#define SERIAL_8N1 0
using portMUX_TYPE = int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
#define portENTER_CRITICAL_ISR(x) ((void)0)
#define portEXIT_CRITICAL_ISR(x) ((void)0)
inline uint32_t testMs=1000, testUs=1000000;
inline int pins[64]={}, duties[64]={};
inline std::array<int,16> pwmChannelPins=[] {std::array<int,16> p{};p.fill(-1);return p;}();
inline bool attachOk=true;
inline uint32_t millis(){return testMs;}
inline uint32_t micros(){return testUs;}
inline void delay(int){}
inline int digitalRead(int p){return pins[p];}
inline void digitalWrite(int p,int v){pins[p]=v;}
inline void pinMode(int,int){}
inline int digitalPinToInterrupt(int p){return p;}
inline long map(long value,long inMin,long inMax,long outMin,long outMax){return (value-inMin)*(outMax-outMin)/(inMax-inMin)+outMin;}
inline void attachInterrupt(int,void(*)(),int){}
template<class T> T constrain(T x,T a,T b){return std::clamp(x,a,b);}
struct String:std::string {
 using std::string::string; String(std::string s):std::string(s){}
 template<class T, typename std::enable_if<std::is_integral<T>::value,int>::type=0>String(T v):std::string(std::to_string(v)){}
 String(unsigned int v,int):std::string(std::to_string(v)){}
 void toCharArray(char*out,size_t n)const{if(n){size_t k=std::min(n-1,size());memcpy(out,data(),k);out[k]=0;}}
};
struct EspMock {bool restarted=false;void restart(){restarted=true;}};inline EspMock ESP;
struct Stream {virtual ~Stream()=default;virtual size_t write(const uint8_t*,size_t)=0;};
struct SerialMock:Stream {std::vector<uint8_t> rx,tx;size_t cursor=0;int capacity=1024;int available(){return int(rx.size()-cursor);}int read(){return cursor<rx.size()?rx[cursor++]:-1;}int availableForWrite(){return capacity;}size_t write(const uint8_t*p,size_t n)override{tx.insert(tx.end(),p,p+n);return n;}void begin(int){} void println(const char* = ""){} template<class T>void print(T){} template<class... A>void printf(const char*,A...){} };
inline SerialMock Serial;
struct HardwareSerial:Stream {int capacity=1024;std::vector<uint8_t> tx,rx;size_t cursor=0; HardwareSerial(int){} void setRxBufferSize(int){} void setTxBufferSize(int){} void begin(int,int,int,int){} int available(){return int(rx.size()-cursor);}int read(){return cursor<rx.size()?rx[cursor++]:-1;}int availableForWrite(){return capacity;}size_t write(const uint8_t*p,size_t n){tx.insert(tx.end(),p,p+n);return n;}};
inline bool ledcAttach(int,int,int){return attachOk;}
inline bool ledcWrite(int p,int v){
#if ESP_ARDUINO_VERSION_MAJOR < 3
 if(p>=0&&p<int(pwmChannelPins.size())&&pwmChannelPins[p]>=0)p=pwmChannelPins[p];
#endif
 duties[p]=v;return true;
}
inline double ledcSetup(int,int,int){return attachOk?20000:0;}
inline void ledcAttachPin(int pin,int channel){pwmChannelPins[channel]=pin;}
