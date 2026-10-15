#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string>
#include <array>
#include <stdarg.h>
#define OUTPUT 1
#define INPUT_PULLUP 2
#define INPUT_PULLDOWN 3
#define CHANGE 4
#define ARDUINO_ISR_ATTR
#define portMUX_INITIALIZER_UNLOCKED 0
using portMUX_TYPE=int;
inline void portENTER_CRITICAL(portMUX_TYPE *) {}
inline void portEXIT_CRITICAL(portMUX_TYPE *) {}
inline void portENTER_CRITICAL_ISR(portMUX_TYPE *) {}
inline void portEXIT_CRITICAL_ISR(portMUX_TYPE *) {}
#define HIGH 1
#define LOW 0
inline uint32_t fakeTime=0;
inline uint64_t fakeMicros=0;
inline std::array<int,64> pins{};
inline std::array<unsigned,64> duties{};
inline std::array<int,8> channelPins{};
inline uint32_t millis() { return fakeTime; }
inline uint32_t micros() { return uint32_t(fakeMicros); }
inline void delay(uint32_t n) { fakeTime+=n; fakeMicros+=uint64_t(n)*1000; }
using ISRCallback=void (*)(void *);
inline std::array<ISRCallback,64> callbacks{};
inline std::array<void *,64> callbackArgs{};
inline void attachInterruptArg(int pin,ISRCallback handler,void *arg,int) { callbacks[pin]=handler; callbackArgs[pin]=arg; }
inline void signalEdge(int pin,int value) { pins[pin]=value; if(callbacks[pin]) callbacks[pin](callbackArgs[pin]); }
inline void pinMode(int p,int mode) { if(mode==INPUT_PULLUP) pins[p]=HIGH; }
inline void digitalWrite(int p,int v) { pins[p]=v; }
inline int digitalRead(int p) { return pins[p]; }
inline bool ledcAttachChannel(int pin,unsigned,int,int channel) { channelPins[channel]=pin; return true; }
inline double ledcSetup(int,unsigned,int) { return 20000; }
inline void ledcAttachPin(int pin,int channel) { channelPins[channel]=pin; }
#include "esp_arduino_version.h"
inline bool ledcWrite(int key,unsigned duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  duties[key]=duty;
#else
  duties[channelPins[key]]=duty;
#endif
  return true;
}
struct FakeSerial {
  void begin(int) {}
  void println(const char *) {}
  void printf(const char *,...) {}
};
inline FakeSerial Serial;
