#pragma once
#include <stdint.h>
#include <math.h>
#include "Config.h"

namespace rover {
inline uint32_t age(uint32_t now, uint32_t then) { return now - then; }
inline float axis(uint16_t us) {
  int delta = int(us) - 1500;
  if (delta >= -config::RC_DEADBAND_US && delta <= config::RC_DEADBAND_US) return 0;
  return delta > 0 ? float(delta - config::RC_DEADBAND_US) / (500-config::RC_DEADBAND_US)
                   : float(delta + config::RC_DEADBAND_US) / (500-config::RC_DEADBAND_US);
}
struct State {
  bool armed = false, inhibited = true, haveRC = false, trackingNeutral = false;
  uint16_t steer = 1500, drive = 1500;
  uint32_t lastRC = 0, neutralSince = 0;
  void stop(bool disarm) {
    if (disarm) armed = false;
    inhibited = true; haveRC = false; trackingNeutral = false;
    steer = drive = 1500;
  }
  void tick(uint32_t now) {
    if (haveRC && age(now,lastRC) >= config::CONTROL_TIMEOUT_MS) stop(true);
  }
  bool neutralReady(uint32_t now) const {
    return haveRC && trackingNeutral && age(now,lastRC) < config::CONTROL_TIMEOUT_MS &&
           age(now,neutralSince) >= config::NEUTRAL_HOLD_MS;
  }
  // Both motion channels must be explicit and fresh in the same frame.
  // 0 releases; 65535 never reuses a possibly stale motion command.
  bool rc(uint16_t s, uint16_t d, uint32_t now) {
    tick(now);
    if (s == 0 || d == 0) { stop(false); return true; }
    if (s < 1000 || s > 2000 || d < 1000 || d > 2000) return false;
    steer=s; drive=d; lastRC=now; haveRC=true;
    if (axis(s)==0 && axis(d)==0) {
      if (!trackingNeutral) { neutralSince=now; trackingNeutral=true; }
      if (neutralReady(now)) inhibited=false;
    } else {
      trackingNeutral=false;
    }
    return true;
  }
  bool arm(uint32_t now) {
    tick(now);
    if (!neutralReady(now)) return false;
    armed=true; inhibited=false; return true;
  }
  void mix(int16_t &left, int16_t &right) const {
    left=right=0;
    if (!armed || inhibited || !haveRC) return;
    const float d=axis(drive), s=axis(steer)*config::STEER_GAIN;
    float l=d+s, r=d-s;
    const float peak=fmaxf(1.0f,fmaxf(fabsf(l),fabsf(r)));
    left=int16_t(lroundf(l/peak*config::MAX_PWM));
    right=int16_t(lroundf(r/peak*config::MAX_PWM));
  }
};

struct Motor {
  int16_t output=0;
  int8_t lastDirection=0;
  bool coasting=false;
  uint32_t coastSince=0;
  void reset() { output=0; lastDirection=0; coasting=false; }
  int16_t update(int16_t target,uint32_t now) {
    const int8_t direction=target>0 ? 1 : target<0 ? -1 : 0;
    if (direction && lastDirection && direction!=lastDirection) {
      if (!coasting) { coasting=true; coastSince=now; }
      output=0;
      if (age(now,coastSince)<config::REVERSAL_COAST_MS) return 0;
      lastDirection=direction; coasting=false;
    } else if (coasting) {
      if (age(now,coastSince)<config::REVERSAL_COAST_MS) return output=0;
      coasting=false;
    }
    if (direction) lastDirection=direction;
    output=target; return output;
  }
};
}
