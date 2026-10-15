#pragma once
#include <stdint.h>

// Select before compile/upload. These are electrical-interface profiles,
// not an automatic identification of the connected board or motor ratings.
// 1=MX1508, 2=DRV8833, 3=TB6612FNG, 4=BTS7960 module, 5=L298N module.
#ifndef TELERC_DRIVER
#define TELERC_DRIVER 1
#endif
#ifndef TELERC_MOTOR_COUNT
#define TELERC_MOTOR_COUNT 4
#endif
#ifndef TELERC_SUPPLY_MAX_MV
#define TELERC_SUPPLY_MAX_MV 5000
#endif
#ifndef TELERC_MOTOR_RATED_MV
#define TELERC_MOTOR_RATED_MV 6000
#endif
#ifndef TELERC_BTS_LOGIC_VERIFIED
#define TELERC_BTS_LOGIC_VERIFIED 0
#endif
#ifndef TELERC_PWM_HZ
#define TELERC_PWM_HZ (TELERC_DRIVER==5 ? 10000 : 20000)
#endif

namespace hardware {
enum class Driver : uint8_t { MX1508=1, DRV8833=2, TB6612=3, BTS7960=4, L298=5 };
constexpr Driver DRIVER=static_cast<Driver>(TELERC_DRIVER);
constexpr uint8_t MOTOR_COUNT=TELERC_MOTOR_COUNT;
// Four physical slots: LF, LR, RF, RR. Two-motor builds use LF and RF only.
constexpr bool active(uint8_t i) { return i<4 && (MOTOR_COUNT==4 || i==0 || i==2); }
constexpr uint8_t ordinal(uint8_t i) { return MOTOR_COUNT==2 ? i/2 : i; }
constexpr bool dualPWM() { return TELERC_DRIVER==1 || TELERC_DRIVER==2 || TELERC_DRIVER==4; }
constexpr uint8_t channelsPerMotor() { return dualPWM() ? 2 : 1; }
constexpr uint8_t PWM_CHANNELS=MOTOR_COUNT*channelsPerMotor();
struct Pins { uint8_t a,b,extra; };
// MX/DRV: a,b = inputs, extra unused.
// TB/L298: a,b = direction, extra = PWM/ENA/ENB.
// BTS: a,b = RPWM/LPWM, extra = both R_EN/L_EN joined on THAT module only.
constexpr Pins MOTORS[4]={{4,5,16},{6,7,17},{8,9,18},{10,11,47}};
constexpr int GLOBAL_ENABLE=(TELERC_DRIVER==2 || TELERC_DRIVER==3) ? 2 : -1;
constexpr uint32_t WAKE_MS=2;
constexpr uint32_t PWM_HZ=TELERC_PWM_HZ;
constexpr uint32_t SUPPLY_MAX_MV=TELERC_SUPPLY_MAX_MV;
constexpr uint32_t MOTOR_RATED_MV=TELERC_MOTOR_RATED_MV;
constexpr uint32_t SUPPLY_MIN_MV=TELERC_DRIVER==2 ? 2700 : TELERC_DRIVER==3 ? 2500 : TELERC_DRIVER==4 ? 5500 : TELERC_DRIVER==5 ? 5000 : 2000;
constexpr uint32_t SUPPLY_LIMIT_MV=TELERC_DRIVER==2 ? 10800 : TELERC_DRIVER==3 ? 13500 : TELERC_DRIVER==4 ? 27500 : TELERC_DRIVER==5 ? 46000 : 8000;
inline const char *driverName() {
  switch(DRIVER) {
    case Driver::MX1508:return "MX1508";
    case Driver::DRV8833:return "DRV8833";
    case Driver::TB6612:return "TB6612FNG";
    case Driver::BTS7960:return "BTS7960-module";
    case Driver::L298:return "L298N-module";
  }
  return "INVALID";
}
static_assert(TELERC_DRIVER>=1 && TELERC_DRIVER<=5,"Unsupported TELERC_DRIVER");
static_assert(TELERC_MOTOR_COUNT==2 || TELERC_MOTOR_COUNT==4,"Only two or four individual motor channels are supported");
static_assert(PWM_CHANNELS<=8,"ESP32-S3 LEDC channel budget exceeded");
static_assert(PWM_HZ>=500 && PWM_HZ<=20000,"PWM frequency outside standard profile range");
static_assert(SUPPLY_MAX_MV>=SUPPLY_MIN_MV && SUPPLY_MAX_MV<=SUPPLY_LIMIT_MV,"Declared supply is outside driver profile range");
static_assert(SUPPLY_MAX_MV<=MOTOR_RATED_MV,"Declared supply exceeds motor voltage rating; PWM cap is not voltage regulation");
static_assert(TELERC_DRIVER!=4 || TELERC_BTS_LOGIC_VERIFIED==1,"Verify BTS module accepts 3.3 V GPIO or install level conversion, then set TELERC_BTS_LOGIC_VERIFIED=1");
}
