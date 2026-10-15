#pragma once
#include <Arduino.h>
#include <esp_arduino_version.h>
#include "Config.h"

namespace motor_output {
inline bool permittedPin(int pin) {
  // Conservative DevKitC-1 map: no boot straps, USB, flash/PSRAM, UART0 or RGB LED.
  return pin==1 || pin==2 || (pin>=4 && pin<=18) || (pin>=39 && pin<=42) || pin==47;
}
inline bool validatePins(const hardware::Pins *map=hardware::MOTORS,int enable=hardware::GLOBAL_ENABLE) {
  bool used[49]={};
  if(config::BOOT_STOP_PIN<0 || config::BOOT_STOP_PIN>48) return false;
  used[config::BOOT_STOP_PIN]=true;
  if(config::STATUS_LED_PIN>=0) {
    if(config::STATUS_LED_PIN>48 || used[config::STATUS_LED_PIN]) return false;
    used[config::STATUS_LED_PIN]=true;
  }
  for(uint8_t pin:config::RX_PINS) {
    if(pin>48 || used[pin]) return false;
    used[pin]=true;
  }
  if(enable>=0) {
    if(!permittedPin(enable) || used[enable]) return false;
    used[enable]=true;
  }
  for(uint8_t i=0;i<4;++i) if(hardware::active(i)) {
    const uint8_t pins[3]={map[i].a,map[i].b,map[i].extra};
    const uint8_t count=(TELERC_DRIVER==1 || TELERC_DRIVER==2) ? 2 : 3;
    for(uint8_t j=0;j<count;++j) {
      if(!permittedPin(pins[j]) || used[pins[j]]) return false;
      used[pins[j]]=true;
    }
  }
  return true;
}
inline uint8_t channel(uint8_t i,uint8_t leg=0) {
  return hardware::ordinal(i)*hardware::channelsPerMotor()+leg;
}
struct Bank {
  bool ready=false, prepared=false, awake=false;
  uint8_t attached=0;
  uint32_t awakeSince=0;
  int16_t written[4]={32767,32767,32767,32767};
  void pwm(uint8_t pin,uint8_t ch,uint8_t duty) {
    if(!(attached&(1u<<ch))) { digitalWrite(pin,LOW); return; }
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(pin,duty);
#else
    ledcWrite(ch,duty);
#endif
  }
  bool attach(uint8_t pin,uint8_t ch) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    if(!ledcAttachChannel(pin,hardware::PWM_HZ,8,ch)) return false;
#else
    if(ledcSetup(ch,hardware::PWM_HZ,8)==0) return false;
    ledcAttachPin(pin,ch);
#endif
    attached|=uint8_t(1u<<ch); pwm(pin,ch,0); return true;
  }
  bool prepare() {
    if(!validatePins()) return false;
    if(hardware::GLOBAL_ENABLE>=0) {
      pinMode(hardware::GLOBAL_ENABLE,OUTPUT); digitalWrite(hardware::GLOBAL_ENABLE,LOW);
    }
    for(uint8_t i=0;i<4;++i) if(hardware::active(i)) {
      const auto &p=hardware::MOTORS[i];
      pinMode(p.a,OUTPUT); digitalWrite(p.a,LOW);
      pinMode(p.b,OUTPUT); digitalWrite(p.b,LOW);
      if(TELERC_DRIVER>=3) { pinMode(p.extra,OUTPUT); digitalWrite(p.extra,LOW); }
    }
    prepared=true; stopAll(); return true;
  }
  bool begin() {
    if(!prepared) return false;
    for(uint8_t i=0;i<4;++i) if(hardware::active(i)) {
      const auto &p=hardware::MOTORS[i];
      const bool ok=hardware::dualPWM() ? attach(p.a,channel(i,0)) && attach(p.b,channel(i,1))
                                       : attach(p.extra,channel(i));
      if(!ok) { ready=false; stopAll(); return false; }
    }
    ready=true; stopAll(); return true;
  }
  void stopAll() {
    if(!prepared) return;
    if(hardware::GLOBAL_ENABLE>=0) digitalWrite(hardware::GLOBAL_ENABLE,LOW);
    for(uint8_t i=0;i<4;++i) if(hardware::active(i)) {
      const auto &p=hardware::MOTORS[i];
      if(TELERC_DRIVER==4) digitalWrite(p.extra,LOW); // Both BTS INH pins off = high impedance.
      if(hardware::dualPWM()) { pwm(p.a,channel(i,0),0); pwm(p.b,channel(i,1),0); }
      else {
        pwm(p.extra,channel(i),0); // L298 EN low; TB STBY already low.
        digitalWrite(p.a,LOW); digitalWrite(p.b,LOW);
      }
      written[i]=32767;
    }
    awake=false;
  }
  void writeMotor(uint8_t i,int16_t demand) {
    if(demand==written[i]) return;
    const auto &p=hardware::MOTORS[i];
    const uint8_t duty=uint8_t(demand<0 ? -demand : demand);
    if(hardware::dualPWM()) {
      if(TELERC_DRIVER==4) digitalWrite(p.extra,LOW);
      if(demand>=0) { pwm(p.b,channel(i,1),0); pwm(p.a,channel(i,0),duty); }
      else { pwm(p.a,channel(i,0),0); pwm(p.b,channel(i,1),duty); }
      if(TELERC_DRIVER==4 && duty) digitalWrite(p.extra,HIGH);
    } else {
      pwm(p.extra,channel(i),0); // Disable/brake before changing direction pins.
      digitalWrite(p.a,demand>0 ? HIGH : LOW);
      digitalWrite(p.b,demand<0 ? HIGH : LOW);
      // TB6612: IN1=IN2=LOW and PWM=HIGH gives high impedance while
      // another motor is moving. PWM=LOW alone would short-brake instead.
      pwm(p.extra,channel(i),duty ? duty : (TELERC_DRIVER==3 ? 255 : 0));
    }
    written[i]=demand;
  }
  bool apply(const int16_t *demands,uint32_t now) {
    if(!ready) { stopAll(); return false; }
    bool any=false;
    for(uint8_t i=0;i<4;++i) if(hardware::active(i) && demands[i]) any=true;
    if(!any) { stopAll(); return true; }
    if(hardware::GLOBAL_ENABLE>=0 && !awake) {
      digitalWrite(hardware::GLOBAL_ENABLE,HIGH); awake=true; awakeSince=now;
      for(uint8_t i=0;i<4;++i) written[i]=32767;
    }
    if(hardware::GLOBAL_ENABLE>=0 && uint32_t(now-awakeSince)<hardware::WAKE_MS) return false;
    for(uint8_t i=0;i<4;++i) if(hardware::active(i)) writeMotor(i,demands[i]);
    return true;
  }
};
inline int16_t limitedDemand(uint8_t index,int16_t demand) {
  int value=int(demand)*config::MOTOR_TRIM_PERCENT[index]/100;
  const int cap=config::MOTOR_DUTY_CAP[index];
  if(value>cap) value=cap;
  if(value<-cap) value=-cap;
  return int16_t(config::MOTOR_INVERT[index] ? -value : value);
}
}
