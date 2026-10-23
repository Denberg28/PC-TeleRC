#pragma once
#include <stdint.h>
namespace fleet {
constexpr uint32_t IDENTITY_MS=90000;
struct Identity {
 uint64_t device=0;uint32_t at=0;bool have=false,conflict=false;
 bool observe(uint64_t value,uint32_t now){
  if(!value)return false;
  if(have&&uint32_t(now-at)<IDENTITY_MS&&device!=value){conflict=true;at=now;return false;}
  if(conflict&&uint32_t(now-at)<IDENTITY_MS)return false;
  device=value;at=now;have=true;conflict=false;return true;
 }
};
inline uint64_t readId(const uint8_t*p){uint64_t v=0;for(unsigned i=0;i<8;++i)v|=uint64_t(p[i])<<(8*i);return v;}
inline void writeId(uint8_t*p,uint64_t v){for(unsigned i=0;i<8;++i)p[i]=v>>(8*i);}
}
