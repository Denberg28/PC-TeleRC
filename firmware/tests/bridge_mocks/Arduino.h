#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <deque>
#include <algorithm>
#include <cstdarg>
inline uint32_t clockMs=0;
inline uint32_t millis(){return clockMs;}
inline void delay(uint32_t n){clockMs+=n;}
constexpr int SERIAL_8N1=0;
class String {
 std::string data;
 public:
 String(const char* p=""):data(p){}
 String(const std::string& p):data(p){}
 size_t length()const{return data.size();}
 const char* c_str()const{return data.c_str();}
 void toCharArray(char* out,size_t n)const{snprintf(out,n,"%s",data.c_str());}
};
struct SerialMock {
 int room=32;
 void begin(int){}
 int availableForWrite(){return room;}
 size_t write(const uint8_t*,size_t n){return n;}
 void print(const char*){}
 template<class T>void println(T){}
 void printf(const char*,...){}
};
inline SerialMock Serial;
struct HardwareSerial {
 std::vector<std::vector<uint8_t>> frames;
 std::deque<uint8_t> input;
 bool shortWrite=false;
 explicit HardwareSerial(int){}
 void setRxBufferSize(int){}
 void begin(uint32_t,int,int,int){}
 int available(){return int(input.size());}
 int read(){auto b=input.front();input.pop_front();return b;}
 size_t write(const uint8_t* p,size_t n){
  size_t sent=shortWrite?n/2:n;
  frames.emplace_back(p,p+sent);return sent;
 }
};
