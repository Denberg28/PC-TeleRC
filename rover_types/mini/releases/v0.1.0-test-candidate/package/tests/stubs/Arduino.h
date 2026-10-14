#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string>
#include <array>
#include <stdarg.h>
#define OUTPUT 1
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0
inline uint32_t fakeTime=0;
inline std::array<int,64> pins{};
inline std::array<unsigned,64> duties{};
inline std::array<int,8> channelPins{};
inline uint32_t millis() { return fakeTime; }
inline void delay(uint32_t n) { fakeTime+=n; }
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
