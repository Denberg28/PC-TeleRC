#pragma once
#include "Protocol.h"

namespace unified {
constexpr uint8_t IDLE=0, MANUAL=1, MISSION=2, HEALTH=3;
constexpr uint32_t AXIS_MS=500, FC_MS=2500;
struct Manual {
 bool ready=false;uint8_t owned=0;uint32_t at[2]={};uint16_t value[2]={1500,1500};
 void latch(){ready=false;owned=0;value[0]=value[1]=1500;}
 bool expired(uint32_t now)const{for(unsigned i=0;i<2;++i)if((owned&(1u<<i))&&uint32_t(now-at[i])>=AXIS_MS)return true;return false;}
 bool centered(uint32_t now)const{return ready&&owned==3&&!expired(now)&&value[0]>=1475&&value[0]<=1525&&value[1]>=1475&&value[1]<=1525;}
 static bool release(const mission::Mav&m){return m.id==70&&(mission::u16(m.payload)==0||mission::u16(m.payload+2)==0);}
 bool accept(const mission::Mav&m,const mission::Gate&fc,uint32_t now){
  const auto*p=m.payload;
  if(m.sys!=255||m.comp!=190)return false;
  const bool fresh=fc.fresh(now)&&uint32_t(now-fc.hbAt)<FC_MS;
  if(m.id==0)return fresh&&m.len>=9&&p[4]==6&&p[5]==8;
  if(m.id==70){
   if(m.len!=18||p[16]!=fc.rover||p[17]!=1)return false;
   for(unsigned i=2;i<8;++i)if(mission::u16(p+2*i)!=65535)return false;
   uint16_t v[2]={mission::u16(p),mission::u16(p+2)};
   for(auto x:v)if(x!=65535&&x!=0&&(x<1000||x>2000))return false;
   if(v[0]==65535&&v[1]==65535)return false;
   if(release(m)){latch();return true;}
   if(!fresh||fc.mode!=0)return false;
   if(expired(now))latch();
   if(!ready&&(v[0]<1475||v[0]>1525||v[1]<1475||v[1]>1525))return false;
   if(!fc.armed)for(auto x:v)if(x!=65535&&(x<1475||x>1525))return false;
   ready=true;
   for(unsigned i=0;i<2;++i)if(v[i]!=65535){value[i]=v[i];at[i]=now;owned|=uint8_t(1u<<i);}
   return true;
  }
  if(fresh&&m.id==76&&m.len>=33&&p[30]==fc.rover&&p[31]==1&&mission::u16(p+28)==400){
   const float arm=mission::real(p);
   for(unsigned i=1;i<7;++i)if(mission::u32(p+i*4)!=0)return false;
   if(arm==0)return true;
   return arm==1&&fc.mode==0&&centered(now);
  }
  return false;
 }
};

// Host profile changes discard old work and need silence; INFO is read-only.
struct Session {
 uint8_t profile=IDLE,rover=0;uint32_t at=0;
 bool claim(uint8_t requested,uint8_t id,uint32_t now){
  if((requested!=MANUAL&&requested!=MISSION)||!id||id>20)return false;
  if(profile!=IDLE&&(profile!=requested||rover!=id)&&uint32_t(now-at)<1500)return false;
  profile=requested;rover=id;at=now;return true;
 }
 bool fresh(uint32_t now)const{return profile!=IDLE&&uint32_t(now-at)<=1500;}
};
}
