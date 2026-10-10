#pragma once
#include "TeleRCWire.h"
#include <mbedtls/md.h>
namespace mesh {
constexpr uint8_t VERSION=1, POLL=1, COMMAND=2;
constexpr size_t HEADER=24, TAG=16, MAX=HEADER+telerc::RADIO_MAX+TAG;
constexpr uint32_t RESPONSE_MS=350, POLL_MS=370, AXIS_MS=500, QUEUE_MS=100;
inline uint16_t u16(const uint8_t*p){return uint16_t(p[0])|(uint16_t(p[1])<<8);}
inline void put16(uint8_t*p,uint16_t v){p[0]=uint8_t(v);p[1]=uint8_t(v>>8);}
struct Packet {
 uint8_t kind=0,hops=0,limit=0;uint16_t network=0,origin=0,dest=0,sender=0;
 uint64_t token=0;uint8_t body[telerc::RADIO_MAX]={};size_t n=0;
};
inline size_t seal(const Packet&p,const uint8_t*key,uint8_t*out){
 if(p.n>telerc::RADIO_MAX||p.hops<1||p.hops>p.limit||p.limit>3||!p.network||!p.origin||!p.dest||!p.sender||!p.token||(p.kind!=POLL&&p.kind!=COMMAND))return 0;
 out[0]='T';out[1]='M';out[2]=VERSION;out[3]=p.kind;
 put16(out+4,p.network);put16(out+6,p.origin);put16(out+8,p.dest);put16(out+10,p.sender);
 out[12]=p.hops;out[13]=p.limit;for(int i=0;i<8;++i)out[14+i]=uint8_t(p.token>>(8*i));
 out[22]=uint8_t(p.n);out[23]=0;if(p.n)memcpy(out+HEADER,p.body,p.n);
 uint8_t tag[32];if(mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),key,32,out,HEADER+p.n,tag))return 0;
 memcpy(out+HEADER+p.n,tag,TAG);return HEADER+p.n+TAG;
}
inline bool open(const uint8_t*in,size_t n,const uint8_t*key,Packet&p){
 if(n<HEADER+TAG||n>MAX||in[0]!='T'||in[1]!='M'||in[2]!=VERSION||in[23]||in[22]>telerc::RADIO_MAX||n!=HEADER+in[22]+TAG)return false;
 uint8_t tag[32];if(mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),key,32,in,HEADER+in[22],tag))return false;
 uint8_t diff=0;for(size_t i=0;i<TAG;++i)diff|=tag[i]^in[HEADER+in[22]+i];if(diff)return false;
 p.kind=in[3];p.network=u16(in+4);p.origin=u16(in+6);p.dest=u16(in+8);p.sender=u16(in+10);p.hops=in[12];p.limit=in[13];p.token=0;
 for(int i=0;i<8;++i)p.token|=uint64_t(in[14+i])<<(8*i);
 p.n=in[22];if(p.n)memcpy(p.body,in+HEADER,p.n);
 return p.network&&p.origin&&p.dest&&p.sender&&p.token&&p.hops>=1&&p.hops<=p.limit&&p.limit<=3&&(p.kind==POLL||p.kind==COMMAND);
}
struct Seen {
 struct Entry {uint64_t token=0;uint16_t origin=0;uint8_t kind=0;uint32_t at=0;};Entry entries[64];size_t next=0;
 bool admit(const Packet&p,uint32_t now){
  for(const auto&e:entries)if(e.token==p.token&&e.origin==p.origin&&e.kind==p.kind&&uint32_t(now-e.at)<4000)return false;
  entries[next]={p.token,p.origin,p.kind,now};next=(next+1)%64;return true;
 }
};
struct Challenge {
 uint64_t token=0;uint32_t at=0;bool active=false;
 void issue(uint64_t t,uint32_t now){token=t;at=now;active=true;}
 bool consume(uint64_t t,uint32_t now){if(!active||token!=t||uint32_t(now-at)>RESPONSE_MS)return false;active=false;return true;}
};
// Fail-closed ownership for CH1/CH2. No telemetry/heartbeat renews either axis.
struct Safety {
 bool ready=false;uint8_t owned=0;uint32_t at[2]={};uint16_t value[2]={1500,1500};
 void latch(){ready=false;owned=0;value[0]=value[1]=1500;}
 bool expired(uint32_t now)const {for(int i=0;i<2;++i)if((owned&(1<<i))&&uint32_t(now-at[i])>=AXIS_MS)return true;return false;}
 bool centered(uint32_t now)const {return ready&&owned==3&&!expired(now)&&value[0]>=1475&&value[0]<=1525&&value[1]>=1475&&value[1]<=1525;}
 bool rc(const uint8_t*p,size_t n,uint32_t now){
  if(!telerc::mavV1(p,n,70,18,124)||p[3]!=255||p[4]!=190||p[22]!=1||p[23]!=1)return false;
  uint16_t v[2]={u16(p+6),u16(p+8)};
  for(int i=2;i<8;++i)if(u16(p+6+2*i)!=65535)return false;
  for(auto x:v)if(x!=65535&&x!=0&&(x<1000||x>2000))return false;
  if(v[0]==65535&&v[1]==65535)return false;
  if(expired(now))latch();
  if(v[0]==0||v[1]==0){latch();return true;}
  if(!ready){if(v[0]<1475||v[0]>1525||v[1]<1475||v[1]>1525)return false;ready=true;}
  for(int i=0;i<2;++i)if(v[i]!=65535){value[i]=v[i];at[i]=now;owned|=uint8_t(1<<i);}
  return true;
 }
};
// Small whitelist: real telemetry only; handles MAVLink 1 and unsigned MAVLink 2.
inline int telemetryClass(const uint8_t*p,size_t n){
 bool v1=n>=8&&p[0]==0xfe&&n==size_t(p[1])+8;
 bool v2=n>=12&&p[0]==0xfd&&p[2]==0&&n==size_t(p[1])+12;
 if(!v1&&!v2)return -1;
 uint32_t id=v1?p[5]:uint32_t(p[7])|(uint32_t(p[8])<<8)|(uint32_t(p[9])<<16);
 uint8_t extra=0;int slot=-1;
 switch(id){case 0:extra=50;slot=1;break;case 77:extra=143;slot=0;break;case 1:extra=124;slot=2;break;case 24:extra=24;slot=2;break;case 33:extra=104;slot=2;break;default:return -1;}
 uint16_t crc=0xffff;for(size_t i=1;i<n-2;++i)crc=telerc::mavCrcByte(crc,p[i]);crc=telerc::mavCrcByte(crc,extra);
 if(p[n-2]!=uint8_t(crc)||p[n-1]!=uint8_t(crc>>8))return -1;
 if(id==0){size_t off=v1?6:10;if(p[1]<9||p[off+4]!=10||(p[off+5]!=3&&p[off+5]!=0)||(v1?(p[3]!=1||p[4]!=1):(p[5]!=1||p[6]!=1)))return -1;}
 return slot;
}
struct MavParser {
 uint8_t data[telerc::UART_MAX]={};size_t used=0,total=0;uint32_t at=0;
 bool feed(uint8_t b,uint32_t now){
  if(used&&uint32_t(now-at)>20)used=total=0;
  at=now;
  if(!used){if(b!=0xfe&&b!=0xfd)return false;data[used++]=b;return false;}
  data[used++]=b;
  if(used==2)total=size_t(data[1])+(data[0]==0xfe?8:12);
  if(used==3&&data[0]==0xfd&&(data[2]&1))total+=13;
  if(total>sizeof(data)){used=total=0;return false;}
  if(total&&used==total){used=0;return true;}return false;
 }
};
}
