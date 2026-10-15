#pragma once
#include <Arduino.h>
#include "RadioControl.h"

namespace receiver {
// All ISR-shared fields are protected by the same ESP32 cross-core spinlock.
struct Capture {
  volatile uint32_t rise=0, lastGood=0, good=0, bad=0;
  volatile uint16_t width=0;
  volatile bool rising=false;
};
struct Sample { uint16_t width; uint32_t lastGood, good, bad; };
static Capture channels[4];
static uint8_t inputPins[4]={config::RX_PINS[0],config::RX_PINS[1],config::RX_PINS[2],config::RX_PINS[3]};
static portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;

static void ARDUINO_ISR_ATTR edge(void *argument) {
  const uint8_t index=uint8_t(reinterpret_cast<uintptr_t>(argument));
  const uint32_t now=micros();
  const bool high=digitalRead(inputPins[index])==HIGH;
  portENTER_CRITICAL_ISR(&mux);
  Capture &c=channels[index];
  if(high) { c.rise=now; c.rising=true; }
  else if(c.rising) {
    const uint32_t width=now-c.rise; c.rising=false;
    if(width>=config::PWM_VALID_MIN_US && width<=config::PWM_VALID_MAX_US) {
      c.width=uint16_t(width); c.lastGood=now; c.good=c.good+1;
    } else c.bad=c.bad+1; // A single glitch does not discard the last valid pulse.
  }
  portEXIT_CRITICAL_ISR(&mux);
}
inline void begin() {
  for(uint8_t i=0;i<4;++i) {
    pinMode(config::RX_PINS[i],INPUT_PULLDOWN);
    attachInterruptArg(config::RX_PINS[i],edge,reinterpret_cast<void *>(uintptr_t(i)),CHANGE);
  }
}
inline radio::Frame snapshot(Sample *output=nullptr) {
  Sample samples[4];
  portENTER_CRITICAL(&mux);
  for(uint8_t i=0;i<4;++i) {
    const Capture &c=channels[i];
    samples[i]={c.width,c.lastGood,c.good,c.bad};
  }
  // Read time after the copy while still locked: an intervening ISR must not
  // create a "future" lastGood timestamp and false timeout via subtraction.
  const uint32_t now=micros();
  portEXIT_CRITICAL(&mux);
  radio::Frame f; f.healthy=true;
  for(uint8_t i=0;i<4;++i) {
    if(output) output[i]=samples[i];
    if(samples[i].good==0 || now-samples[i].lastGood>=config::RX_TIMEOUT_US) f.healthy=false;
  }
  f.steer=radio::normalize(samples[0].width,config::RX_STEER_INVERT);
  f.drive=radio::normalize(samples[1].width,config::RX_DRIVE_INVERT);
  f.arm=samples[2].width; f.selector=samples[3].width;
  return f;
}
}
