#pragma once
#include <stdint.h>

namespace telerc {
// Receive-link indication only. Never grants control or refreshes a failsafe.
struct LinkLed {
 static constexpr uint32_t PEER_TIMEOUT_MS=500, BLINK_HALF_MS=250;
 uint32_t peerAt=0;
 bool havePeer=false;
 void received(uint32_t now){peerAt=now;havePeer=true;}
 bool on(uint32_t now,bool radioReady,uint32_t timeoutMs=PEER_TIMEOUT_MS)const{
  if(radioReady&&havePeer&&uint32_t(now-peerAt)<timeoutMs)return true;
  return (now/BLINK_HALF_MS)%2==0;
 }
};
}
