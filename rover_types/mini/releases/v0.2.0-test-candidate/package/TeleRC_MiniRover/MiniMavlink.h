#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Deliberately small MAVLink subset, no external libraries.
// Commands: HEARTBEAT(0), RC_CHANNELS_OVERRIDE(70), COMMAND_LONG(76).
// Telemetry: HEARTBEAT(0), COMMAND_ACK(77). See MAVLink common.xml.
namespace mini_mav {
inline uint16_t accumulate(uint16_t crc,uint8_t value) {
  uint8_t tmp=value ^ uint8_t(crc); tmp ^= uint8_t(tmp<<4);
  return (crc>>8) ^ (uint16_t(tmp)<<8) ^ (uint16_t(tmp)<<3) ^ (tmp>>4);
}
inline uint16_t u16(const uint8_t *p) { return uint16_t(p[0]) | uint16_t(p[1])<<8; }
inline void put16(uint8_t *p,uint16_t v) { p[0]=uint8_t(v); p[1]=uint8_t(v>>8); }
struct Message {
  uint8_t id=0, system=0, component=0, length=0;
  uint8_t payload[38] = {};
};
inline bool decode(const uint8_t *data,size_t n,Message &m,size_t &consumed) {
  consumed=0; m=Message{};
  if (n<8 || (data[0]!=0xfe && data[0]!=0xfd)) return false;
  const bool v2=data[0]==0xfd;
  const size_t header=v2 ? 10 : 6;
  if (n<header+2) return false;
  // No signing support: reject every incompatible flag, including signing.
  if (v2 && (data[2]!=0 || data[8]!=0 || data[9]!=0)) return false;
  const uint8_t id=data[v2 ? 7 : 5], len=data[1];
  const size_t total=header+len+2;
  if (n<total) return false;
  uint8_t minimum=0, maximum=0, extra=0;
  switch(id) {
    case 0: minimum=maximum=9; extra=50; break;
    case 70: minimum=18; maximum=v2 ? 38 : 18; extra=124; break;
    case 76: minimum=maximum=33; extra=152; break;
    default: return false;
  }
  // MAVLink 2 may truncate trailing zero bytes (including target component).
  if ((!v2 && len!=minimum) || (v2 && (len==0 || len>maximum))) return false;
  uint16_t crc=0xffff;
  for(size_t i=1;i<header+len;++i) crc=accumulate(crc,data[i]);
  if (accumulate(crc,extra)!=u16(data+header+len)) return false;
  m.id=id; m.system=data[v2 ? 5 : 3]; m.component=data[v2 ? 6 : 4];
  m.length=len; memcpy(m.payload,data+header,len); consumed=total;
  return true;
}
inline size_t encode(uint8_t *out,uint8_t sequence,uint8_t system,uint8_t component,
                     uint8_t id,const uint8_t *payload,uint8_t len,uint8_t extra) {
  out[0]=0xfe; out[1]=len; out[2]=sequence; out[3]=system; out[4]=component; out[5]=id;
  memcpy(out+6,payload,len);
  uint16_t crc=0xffff;
  for(size_t i=1;i<size_t(len)+6;++i) crc=accumulate(crc,out[i]);
  put16(out+6+len,accumulate(crc,extra)); return len+8;
}
}
