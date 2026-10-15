#pragma once
#include "RoverCore.h"

namespace radio {
enum class Source : uint8_t { Stop=0, Transmitter=1, PC=2 };
inline const char *name(Source s) {
  return s==Source::Transmitter ? "TX" : s==Source::PC ? "PC" : "STOP";
}
struct Frame {
  bool healthy=false;
  uint16_t steer=1500, drive=1500, arm=1500, selector=1500;
};
inline uint16_t normalize(uint16_t us,bool invert) {
  if(us<1000) us=1000;
  if(us>2000) us=2000;
  return invert ? uint16_t(3000-us) : us;
}
struct Gate {
  Source selected=Source::Stop, pending=Source::Stop;
  bool permit=false, offSeen=false, previousHigh=true;
  bool pendingValid=false, neutralTracking=false;
  uint32_t pendingSince=0, neutralSince=0;
  void reset() {
    selected=pending=Source::Stop; permit=false; offSeen=false;
    previousHigh=true; pendingValid=false; neutralTracking=false;
  }
  bool neutralReady(uint32_t now) const {
    return neutralTracking && rover::age(now,neutralSince)>=config::NEUTRAL_HOLD_MS;
  }
  void update(const Frame &f,uint32_t now) {
    const bool armLow=f.arm<=config::SWITCH_LOW_MAX;
    const bool armHigh=f.arm>=config::SWITCH_HIGH_MIN;
    if(!f.healthy || (!armLow && !armHigh)) { reset(); return; }
    const Source request=f.selector<=config::SWITCH_LOW_MAX ? Source::Transmitter :
      f.selector>=config::SWITCH_HIGH_MIN ? Source::PC : Source::Stop;
    if(request==Source::Stop) { reset(); return; }
    if(!pendingValid || request!=pending) {
      reset(); pending=request; pendingSince=now; pendingValid=true; return;
    }
    if(selected!=request) {
      if(rover::age(now,pendingSince)<config::SELECTOR_HOLD_MS) return;
      selected=request; previousHigh=armHigh; offSeen=false; neutralTracking=false;
    }
    const bool centered=rover::axis(f.steer)==0 && rover::axis(f.drive)==0;
    if(centered) {
      if(!neutralTracking) { neutralTracking=true; neutralSince=now; }
    } else neutralTracking=false;
    if(armLow) { permit=false; offSeen=true; }
    else if(!previousHigh) {
      // Only this explicit OFF -> ON edge may establish permission. A rejected
      // edge is consumed; centering later while ON must not arm automatically.
      permit=offSeen && neutralReady(now); offSeen=false;
    }
    previousHigh=armHigh;
  }
};
}
