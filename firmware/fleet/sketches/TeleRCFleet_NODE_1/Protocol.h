#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

namespace mission {
constexpr size_t MAX_MAV=100, MAX_PLAIN=50+MAX_MAV;
constexpr uint8_t VERSION=1, SYNC=1, RESPONSE=2, DATA=3;
constexpr uint32_t TOKEN_MS=2400, HOST_MS=1500, FC_MS=3500;
constexpr uint16_t MAX_ITEMS=200;
inline uint16_t u16(const uint8_t*p){return p[0]|uint16_t(p[1])<<8;}
inline uint32_t u32(const uint8_t*p){return u16(p)|uint32_t(u16(p+2))<<16;}
inline void put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}
inline float real(const uint8_t*p){float v;memcpy(&v,p,4);return v;}
inline uint16_t acc(uint16_t c,uint8_t b){uint8_t t=b^uint8_t(c);t^=t<<4;return (c>>8)^(uint16_t(t)<<8)^(uint16_t(t)<<3)^(t>>4);}
inline uint16_t crc(const uint8_t*p,size_t n){uint16_t c=0xffff;while(n--)c=acc(c,*p++);return c;}
inline bool equal(const uint8_t*a,const uint8_t*b,size_t n){uint8_t v=0;while(n--)v|=*a++^*b++;return v==0;}
struct Frame {
 uint8_t data[MAX_MAV]={};size_t n=0;uint32_t at=0;
 void clear(){n=0;}
 bool fresh(uint32_t now,uint32_t age=HOST_MS)const{return n&&uint32_t(now-at)<=age;}
 bool set(const uint8_t*p,size_t len,uint32_t now){if(!len||len>MAX_MAV)return false;memcpy(data,p,len);n=len;at=now;return true;}
};
struct Mav {
 uint8_t bytes[MAX_MAV]={},payload[80]={};size_t n=0;uint8_t sys=0,comp=0,len=0;uint32_t id=0;
 static int extra(uint32_t id){switch(id){
 case 0:return 50;case 1:return 124;case 20:return 214;case 22:return 220;
 case 24:return 24;case 30:return 39;case 33:return 104;case 39:return 254;
 case 40:return 230;case 42:return 28;case 43:return 132;case 44:return 221;
 case 46:return 11;case 47:return 153;case 51:return 196;case 70:return 124;case 73:return 38;
 case 76:return 152;case 77:return 143;case 253:return 83;default:return -1;}}
 bool parse(const uint8_t*p,size_t size){
  if(size<8||size>MAX_MAV||(p[0]!=0xfe&&p[0]!=0xfd))return false;
  const bool v2=p[0]==0xfd;size_t head=v2?10:6;
  if(size!=head+p[1]+2||p[1]>sizeof(payload)||(v2&&p[2]!=0))return false;
  id=v2?(uint32_t(p[7])|uint32_t(p[8])<<8|uint32_t(p[9])<<16):p[5];
  int ex=extra(id);if(ex<0)return false;
  uint16_t c=crc(p+1,head-1+p[1]);c=acc(c,ex);
  if(c!=u16(p+head+p[1]))return false;
  memset(payload,0,sizeof(payload));memcpy(payload,p+head,p[1]);
  len=p[1];sys=p[v2?5:3];comp=p[v2?6:4];memcpy(bytes,p,size);n=size;return true;
 }
};
// Parser recovers from partial serial frames. Unknown/signed MAVLink is denied.
struct MavStream {
 uint8_t buf[MAX_MAV]={};size_t used=0,total=0;uint32_t at=0;
 bool feed(uint8_t b,uint32_t now,Mav&out){
  if(used&&uint32_t(now-at)>100)used=total=0;
  at=now;
  if(!used){if(b!=0xfe&&b!=0xfd)return false;buf[used++]=b;return false;}
  buf[used++]=b;
  if(used==2)total=buf[1]+(buf[0]==0xfd?12:8);
  if(used==3&&buf[0]==0xfd&&(buf[2]&1))total+=13;
  if(total>sizeof(buf)){used=total=0;return false;}
  if(used==total){used=0;return out.parse(buf,total);}return false;
 }
};
struct Challenge {
 uint8_t token[16]={};uint32_t at=0;bool active=false;
 void issue(const uint8_t*p,uint32_t now){memcpy(token,p,16);at=now;active=true;}
 bool consume(const uint8_t*p,uint32_t now){
  if(!active||uint32_t(now-at)>TOKEN_MS||!equal(token,p,16))return false;
  active=false;return true;
 }
};
// Mission validator is separate from the manual validator and never allows RC overrides.
struct Gate {
 uint8_t rover=1;bool haveHb=false,armed=false,verifiedUpload=false,started=false;
 uint32_t hbAt=0,bootMs=0;bool haveBoot=false;uint32_t mode=0;
 uint16_t count=0;uint8_t seen[(MAX_ITEMS+7)/8]={};bool uploading=false;uint32_t uploadAt=0;
 explicit Gate(uint8_t id=1):rover(id){}
 void invalidate(){verifiedUpload=false;started=false;uploading=false;count=0;memset(seen,0,sizeof(seen));}
 bool fresh(uint32_t now)const{return haveHb&&uint32_t(now-hbAt)<=FC_MS;}
 void tick(uint32_t now){if(!fresh(now)){haveHb=false;invalidate();}if(uploading&&uint32_t(now-uploadAt)>60000)invalidate();}
 bool allSeen()const{if(!count)return false;for(unsigned i=0;i<count;++i)if(!(seen[i/8]&(1u<<(i%8))))return false;return true;}
 bool fromFc(const Mav&m,uint32_t now){
  if(m.sys!=rover||m.comp!=1)return false;
  auto p=m.payload;
  if(m.id==0){if(m.len<9||p[4]!=10||p[5]!=3)return false;mode=u32(p);armed=p[6]&128;hbAt=now;haveHb=true;}
  // A decreasing FC boot counter invalidates an upload/start authorization.
  if(m.id==33&&m.len>=4){uint32_t t=u32(p);if(haveBoot&&int32_t(t-bootMs)<0)invalidate();bootMs=t;haveBoot=true;}
  if(m.id==47&&p[0]==255&&p[1]==190&&p[3]==0){
   verifiedUpload=uploading&&allSeen()&&p[2]==0;uploading=false;
  }
  return true;
 }
 bool target(const uint8_t*p,size_t pos)const{return p[pos]==rover&&p[pos+1]==1;}
 bool down(const Mav&m,uint32_t now,uint16_t servoMask=0){
  if(m.sys!=255||m.comp!=190)return false;
  auto p=m.payload;
  if(m.id==0)return m.len>=9&&p[4]==6&&p[5]==8; // actual host only
  if(!fresh(now))return false;
  if(m.id==20)return target(p,2)&&m.len>=4;
  if(m.id==43)return target(p,0)&&p[2]==0;
  if(m.id==40||m.id==51)return target(p,2)&&p[4]==0;
  if(m.id==47)return target(p,0)&&p[3]==0;
  bool mutablePlan=!armed&&(mode==0||mode==4);
  if(m.id==44){
   if(!mutablePlan||!target(p,2)||p[4]!=0||u16(p)<2||u16(p)>MAX_ITEMS)return false;
   uint16_t next=u16(p);
   // Protocol re-sends of MISSION_COUNT do not erase received-item tracking.
   if(!uploading||count!=next){invalidate();count=next;uploading=true;}
   uploadAt=now;return true;
  }
  if(m.id==39||m.id==73){
   if(!mutablePlan||!uploading||!target(p,32)||p[37]!=0||p[36]!=1||u16(p+28)>=count)return false;
   uint16_t cmd=u16(p+30),seq=u16(p+28);
   for(unsigned j=0;j<4;++j)if(!isfinite(real(p+j*4)))return false;
   if(!isfinite(real(p+24)))return false;
   if(cmd==16){
    if(m.id==73){int32_t lat=int32_t(u32(p+16)),lon=int32_t(u32(p+20));
     if((p[34]!=5&&p[34]!=6)||lat<-900000000||lat>900000000||lon<-1800000000||lon>1800000000)return false;
    }else if((p[34]!=0&&p[34]!=3)||!isfinite(real(p+16))||!isfinite(real(p+20))||fabs(real(p+16))>90||fabs(real(p+20))>180)return false;
   }else if(cmd==93){if(p[34]!=2||real(p)<2||real(p)>10||real(p+4)!=-1||real(p+8)!=-1||real(p+12)!=-1||u32(p+16)||u32(p+20))return false;}
   else if(cmd==112){if(p[34]!=2||real(p)<0.5f||real(p)>5||real(p+4)!=0||real(p+8)!=0||real(p+12)!=0||u32(p+16)||u32(p+20))return false;}
   else if(cmd==178){if(real(p)!=1||real(p+4)<=0||real(p+4)>3||real(p+8)!=-1)return false;}
   else if(cmd==183){float ch=real(p),pwm=real(p+4);if(ch<1||ch>16||ch!=floorf(ch)||(ch>=5&&ch<=8)||!(servoMask&(1u<<(int(ch)-1)))||pwm<1000||pwm>2000)return false;}
   else return false;
   seen[seq/8]|=1u<<(seq%8);uploadAt=now;return true;
  }
  if(m.id==76&&target(p,30)){
   uint16_t command=u16(p+28);
   // HOLD is always available with a fresh FC; it does not disarm.
   if(command==176)return real(p)==1&&real(p+4)==4;
   // Fleet arming is deliberate, normal FC arming only. Never allow force or
   // arbitrary modes. A mission must be uploaded before ARM. Disarm follows HOLD.
   if(command==400&&m.len>=32&&(mode==0||mode==4)){
    for(unsigned i=1;i<7;++i)if(u32(p+i*4)!=0)return false;
    const float arm=real(p);
    if(arm==0)return true;
    return arm==1&&!armed&&mode==4&&verifiedUpload&&!started;
   }
   if(command==300&&verifiedUpload&&!started&&armed&&(mode==0||mode==4)&&real(p)==0&&real(p+4)==0){started=true;return true;}
  }
  return false;
 }
};
// USB: A5 5A, rover ID, type (1 MAV / 2 status), length LE16, bytes, CRC16.
struct HostStream {
 uint8_t buf[MAX_MAV+8]={};size_t used=0,total=0;uint32_t at=0;
 bool feed(uint8_t b,uint32_t now){
  if(used&&uint32_t(now-at)>100)used=total=0;at=now;
  if(!used){if(b!=0xa5)return false;buf[used++]=b;return false;}
  if(used==1&&b!=0x5a){used=b==0xa5?1:0;return false;}
  buf[used++]=b;
  if(used==6){size_t n=u16(buf+4);if(!n||n>MAX_MAV){used=0;return false;}total=n+8;}
  if(total&&used==total){used=0;return crc(buf+2,total-4)==u16(buf+total-2);}return false;
 }
};
}
