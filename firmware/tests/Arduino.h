#pragma once
#include "esp_arduino_version.h"
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <string>
using std::min;
#define IRAM_ATTR
#define OUTPUT 1
#define INPUT_PULLDOWN 2
#define LOW 0
#define CHANGE 3
using portMUX_TYPE = int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL_ISR(x) ((void)0)
#define portEXIT_CRITICAL_ISR(x) ((void)0)
#define portENTER_CRITICAL(x) ((void)0)
#define portEXIT_CRITICAL(x) ((void)0)
inline uint32_t clockUs = 0;
inline int levels[64] = {};
inline int duties[64] = {};
inline int channelPins[8] = {};
inline bool attachOk = true;
inline uint32_t micros() { return clockUs; }
inline uint32_t millis() { return clockUs / 1000; }
inline int digitalRead(int pin) { return levels[pin]; }
inline void digitalWrite(int pin, int v) { levels[pin] = v; }
inline void pinMode(int, int) {}
inline int digitalPinToInterrupt(int p) { return p; }
inline void attachInterrupt(int, void (*)(), int) {}
template<class T> T constrain(T v, T a, T b) { return std::max(a, std::min(v, b)); }
inline long map(long v,long a,long b,long c,long d) { return (v-a)*(d-c)/(b-a)+c; }
inline bool ledcAttach(int, uint32_t, uint8_t) { return attachOk; }
inline double ledcSetup(int, uint32_t freq, uint8_t) { return attachOk ? freq : 0; }
inline void ledcAttachPin(int p, int ch) { channelPins[ch] = p; }
inline bool ledcWrite(int p, int v) {
#if ESP_ARDUINO_VERSION_MAJOR < 3
  p = channelPins[p];
#endif
  duties[p] = v; return true;
}
struct SerialMock {
  std::string output;
  uint32_t txTimeoutMs=100;
  bool busy=false;
  void setTxTimeoutMs(uint32_t ms) { txTimeoutMs=ms; }
  void begin(int) {}
  int availableForWrite() { if(busy)clockUs+=txTimeoutMs*1000; return 32; }
  size_t write(const uint8_t* p, size_t n) { if(busy)clockUs+=txTimeoutMs*1000; output.append(reinterpret_cast<const char*>(p), n); return n; }
};
inline SerialMock Serial;

