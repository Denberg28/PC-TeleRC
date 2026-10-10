#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace telerc {
constexpr size_t UART_MAX = 280;
constexpr size_t RADIO_MAX = 96;
constexpr uint32_t HOST_FRESH_MS = 200;
inline uint16_t crc16(const uint8_t *p, size_t n) {
  uint16_t c=0xffff;
  while(n--) { c^=uint16_t(*p++)<<8; for(int i=0;i<8;++i)c=(c&0x8000)?uint16_t((c<<1)^0x1021):uint16_t(c<<1); }
  return c;
}
// UART: A5 5A, uint16 LE payload length, payload, CRC16-CCITT over length+payload.
inline size_t encodeUart(const uint8_t *p,size_t n,uint8_t *out) {
  if(!n || n>UART_MAX)return 0;
  out[0]=0xa5;out[1]=0x5a;out[2]=uint8_t(n);out[3]=uint8_t(n>>8);
  memcpy(out+4,p,n);auto c=crc16(out+2,n+2);out[n+4]=uint8_t(c);out[n+5]=uint8_t(c>>8);return n+6;
}
struct UartParser {
  uint8_t data[UART_MAX+6]={};size_t used=0,expected=0;uint32_t last=0;
  void reset(){used=expected=0;}
  bool feed(uint8_t b,uint32_t now) {
    if(used && uint32_t(now-last)>20)reset();
    last=now;
    if(!used) {if(b==0xa5)data[used++]=b;return false;}
    if(used==1 && b!=0x5a){reset();if(b==0xa5)data[used++]=b;return false;}
    data[used++]=b;
    if(used==4){size_t n=size_t(data[2])|(size_t(data[3])<<8);if(!n||n>UART_MAX){reset();return false;}expected=n+6;}
    if(expected && used==expected){size_t n=expected-6;auto c=crc16(data+2,n+2);bool ok=data[n+4]==uint8_t(c)&&data[n+5]==uint8_t(c>>8);reset();return ok;}
    return false;
  }
  size_t length()const{return size_t(data[2])|(size_t(data[3])<<8);}
};
inline uint16_t mavCrcByte(uint16_t c,uint8_t v){uint8_t t=v^(c&255);t^=t<<4;return(c>>8)^(uint16_t(t)<<8)^(uint16_t(t)<<3)^(t>>4);}
inline bool mavV1(const uint8_t *p,size_t n,uint8_t id,uint8_t len,uint8_t extra) {
  if(n!=size_t(len)+8||p[0]!=0xfe||p[1]!=len||p[5]!=id)return false;
  uint16_t c=0xffff;for(size_t i=1;i<n-2;++i)c=mavCrcByte(c,p[i]);c=mavCrcByte(c,extra);
  return p[n-2]==uint8_t(c)&&p[n-1]==uint8_t(c>>8);
}
inline bool textEquals(const uint8_t *p,size_t n,const char*s){return n==strlen(s)&&memcmp(p,s,n)==0;}
// Radio control body: zero or more uint8 length + one original TeleRC datagram.
// Each is independently consumed by the original motor parser, preserving sparse overrides/release semantics.
struct CommandMailbox {
  uint8_t rc[26]={},hb[17]={},event[48]={},release[26]={};
  size_t rcN=0,hbN=0,eventN=0,releaseN=0;
  uint32_t rcAt=0,hbAt=0,eventAt=0,releaseAt=0,axisAt[4]={};
  uint16_t axisValue[4]={};uint8_t pendingAxes=0;uint32_t dropped=0;
  void clearRc(){rcN=0;pendingAxes=0;}
  void clear(){clearRc();hbN=eventN=releaseN=0;}
  bool disarmPending()const{
    return mavV1(event,eventN,76,33,152)&&event[6]==0&&event[7]==0&&event[8]==0&&event[9]==0;
  }
  bool accept(const uint8_t*p,size_t n,uint32_t now) {
    if(textEquals(p,n,"TELERC_DISCONNECT_V1")){clear();memcpy(event,p,n);eventN=n;eventAt=now;return true;}
    if(textEquals(p,n,"TELERC_DISCOVER_V1")){if(!eventN&&!releaseN){memcpy(event,p,n);eventN=n;eventAt=now;}return true;}
    if(textEquals(event,eventN,"TELERC_DISCONNECT_V1")){++dropped;return false;}
    if(n<6||p[3]!=255||p[4]!=190){++dropped;return false;}
    if(mavV1(p,n,70,18,124)){
      if(p[22]!=1||p[23]!=1){++dropped;return false;}
      bool touched=false;
      for(size_t ch=0;ch<8;++ch){
        uint16_t value=uint16_t(p[6+2*ch])|(uint16_t(p[7+2*ch])<<8);
        if(value==0xffff)continue;
        if(ch>=4 || (value!=0 && (value<1000||value>2000))){++dropped;return false;}
        touched=true;
      }
      if(!touched){++dropped;return false;}
      bool isRelease=(p[6]==0&&p[7]==0) || (p[8]==0&&p[9]==0);
      if(isRelease){
        clearRc();
        if(!disarmPending())eventN=0; // release cancels ARM/discovery, but retains DISARM
        if(releaseN){
          // Preserve earlier released channels when separate sparse releases arrive.
          for(size_t ch=0;ch<4;++ch)if(release[6+2*ch]==0&&release[7+2*ch]==0){
            axisValue[ch]=0;
          }else axisValue[ch]=uint16_t(p[6+2*ch])|(uint16_t(p[7+2*ch])<<8);
          memcpy(release,p,n);
          for(size_t ch=0;ch<4;++ch){release[6+2*ch]=uint8_t(axisValue[ch]);release[7+2*ch]=uint8_t(axisValue[ch]>>8);}
          checksumRc(release);
        }else memcpy(release,p,n);
        releaseN=n;releaseAt=now;return true;
      }
      if(releaseN || disarmPending()){++dropped;return false;}
      // Coalesce axes, not whole packets. Ignore values never renew another axis.
      memcpy(rc,p,n);rcN=n;rcAt=now;
      for(size_t ch=0;ch<4;++ch){
        uint16_t value=uint16_t(p[6+2*ch])|(uint16_t(p[7+2*ch])<<8);
        if(value!=0xffff){axisValue[ch]=value;axisAt[ch]=now;pendingAxes|=uint8_t(1<<ch);}
      }
      return true;
    }
    if(mavV1(p,n,0,9,50)){memcpy(hb,p,n);hbN=n;hbAt=now;return true;}
    if(mavV1(p,n,76,33,152)){
      bool isDisarm=p[6]==0&&p[7]==0&&p[8]==0&&p[9]==0;
      bool isArm=p[6]==0&&p[7]==0&&p[8]==0x80&&p[9]==0x3f;
      if(p[34]!=0x90||p[35]!=1||p[36]!=1||p[37]!=1||p[38]!=0||(!isArm&&!isDisarm)){++dropped;return false;}
      for(size_t i=10;i<34;++i)if(p[i]!=0){++dropped;return false;}
      if(!isDisarm && (releaseN || (eventN&&!textEquals(event,eventN,"TELERC_DISCOVER_V1")))){++dropped;return false;}
      if(isDisarm)clearRc();
      memcpy(event,p,n);eventN=n;eventAt=now;return true;
    }
    ++dropped;return false;
  }
  static void checksumRc(uint8_t*p){
    uint16_t c=0xffff;for(size_t i=1;i<24;++i)c=mavCrcByte(c,p[i]);c=mavCrcByte(c,124);
    p[24]=uint8_t(c);p[25]=uint8_t(c>>8);
  }
  size_t take(uint8_t*out,uint32_t now) {
    size_t used=0;
    auto append=[&](uint8_t*p,size_t &n,uint32_t at){if(n&&uint32_t(now-at)<=HOST_FRESH_MS && used+1+n<=RADIO_MAX){out[used++]=uint8_t(n);memcpy(out+used,p,n);used+=n;}n=0;};
    if(textEquals(event,eventN,"TELERC_DISCONNECT_V1")){append(event,eventN,eventAt);clear();return used;}
    if(releaseN || disarmPending()){
      append(release,releaseN,releaseAt);append(event,eventN,eventAt);append(hb,hbN,hbAt);clearRc();return used;
    }
    if(rcN){
      bool fresh=false;
      for(size_t ch=0;ch<4;++ch){
        bool valid=(pendingAxes&(1<<ch))&&uint32_t(now-axisAt[ch])<=HOST_FRESH_MS;
        uint16_t value=valid?axisValue[ch]:0xffff;
        rc[6+2*ch]=uint8_t(value);rc[7+2*ch]=uint8_t(value>>8);fresh|=valid;
      }
      if(fresh){checksumRc(rc);append(rc,rcN,now);}else rcN=0;
      pendingAxes=0;
    }
    append(event,eventN,eventAt);append(hb,hbN,hbAt);return used;
  }
};
inline bool validBundle(const uint8_t*p,size_t n){if(n>RADIO_MAX)return false;size_t i=0;while(i<n){size_t k=p[i++];if(!k||k>48||k>n-i)return false;i+=k;}return i==n;}
// One-use challenge response; no response can renew control twice or arrive after its window.
struct ChallengeWindow {
  uint64_t token=0;uint32_t issued=0;bool open=false;
  void issue(uint64_t t,uint32_t now){token=t;issued=now;open=true;}
  bool consume(uint64_t t,uint32_t now){if(!open||t!=token||uint32_t(now-issued)>90)return false;open=false;return true;}
};
}
