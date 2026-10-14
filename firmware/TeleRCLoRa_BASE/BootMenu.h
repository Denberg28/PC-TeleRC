#pragma once
#include <stdint.h>
namespace telerc {
enum class Press {NONE,TAP,HOLD};
struct BootButton {
 bool raw=false,stable=false,longSent=false;uint32_t changed=0,down=0;
 Press update(bool pressed,uint32_t now){
  if(pressed!=raw){raw=pressed;changed=now;}
  if(raw!=stable&&uint32_t(now-changed)>=30){
   stable=raw;
   if(stable){down=now;longSent=false;}
   else if(!longSent)return Press::TAP;
  }
  if(stable&&!longSent&&uint32_t(now-down)>=1000){longSent=true;return Press::HOLD;}
  return Press::NONE;
 }
};
}
