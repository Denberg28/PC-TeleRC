#define TELERC_HOST_TEST 1
#include <cassert>
#include <iostream>
#include <random>
#include "../TeleRC_MiniRover/TeleRC_MiniRover.ino"

const IPAddress PC(192,168,4,2), OTHER(192,168,4,3);
std::vector<uint8_t> frame(uint8_t id,const std::vector<uint8_t> &payload,uint8_t extra,
                           uint8_t sys=255,uint8_t comp=190) {
  uint8_t out[300]; size_t n=mini_mav::encode(out,7,sys,comp,id,payload.data(),payload.size(),extra);
  return {out,out+n};
}
std::vector<uint8_t> rcFrame(uint16_t s,uint16_t d,uint8_t target=1) {
  std::vector<uint8_t> p(18,255); mini_mav::put16(p.data(),s); mini_mav::put16(p.data()+2,d);
  p[16]=target; p[17]=1; return frame(70,p,124);
}
std::vector<uint8_t> command(float arm,uint16_t id=400,float force=0) {
  std::vector<uint8_t> p(33,0); memcpy(p.data(),&arm,4); memcpy(p.data()+4,&force,4);
  mini_mav::put16(p.data()+28,id); p[30]=1; p[31]=1; return frame(76,p,152);
}
void deliver(const std::vector<uint8_t> &data,IPAddress source=PC,uint16_t port=14550) {
  udp.incoming.push_back({source,port,data}); loop();
}
void discover(IPAddress source=PC) {
  deliver({reinterpret_cast<const uint8_t *>(DISCOVERY),reinterpret_cast<const uint8_t *>(DISCOVERY)+sizeof(DISCOVERY)-1},source);
}
void advance(uint32_t ms) { fakeTime+=ms; loop(); }
void neutral() { deliver(rcFrame(1500,1500)); for(int i=0;i<6;++i) { fakeTime+=50; deliver(rcFrame(1500,1500)); } }
bool allZero() { for(auto &pair:config::MOTOR_PINS) for(int pin:pair) if(duties[pin]) return false; return true; }
// Independent bit-at-a-time X.25 CRC reference; does not use firmware helper.
uint16_t referenceCRC(const uint8_t *p,size_t n,uint8_t extra) {
  uint16_t crc=0xffff;
  for(size_t i=0;i<=n;++i) {
    crc ^= i<n ? p[i] : extra;
    for(int bit=0;bit<8;++bit) crc=(crc&1) ? (crc>>1)^0x8408 : crc>>1;
  }
  return crc;
}
int main() {
  setup(); assert(allZero() && !state.armed && peer==ZERO_IP);
  deliver(rcFrame(1500,2000)); assert(!state.haveRC); // no discovery, no motion
  discover(); assert(peer==PC && !state.armed && udp.outgoing.back().data[5]==0);
  deliver(command(1)); assert(!state.armed && udp.outgoing[udp.outgoing.size()-2].data[8]==2);
  deliver(rcFrame(1500,2000)); deliver(command(1)); assert(!state.armed);
  neutral(); deliver(command(1)); assert(state.armed && !state.inhibited);
  fakeTime+=5; deliver(rcFrame(1500,2000)); assert(duties[4]==config::MAX_PWM && duties[8]==config::MAX_PWM);
  assert(duties[5]==0 && duties[9]==0);
  fakeTime+=5; deliver(rcFrame(2000,2000)); assert(duties[4]==config::MAX_PWM && duties[8]<duties[4]);
  auto bad=rcFrame(1500,1000); bad.back()^=1;
  const auto oldRC=state.lastRC; deliver(bad); assert(state.lastRC==oldRC);
  deliver(rcFrame(1500,1000),OTHER); assert(peer==PC && state.lastRC==oldRC);
  deliver(rcFrame(1500,1000),PC,1234); assert(state.lastRC==oldRC);
  deliver(rcFrame(1500,1000,2)); assert(state.lastRC==oldRC);
  auto spoof=rcFrame(1500,1000); spoof[3]=254; // recompute CRC to test source filter
  uint16_t c=0xffff; for(size_t i=1;i<24;++i)c=mini_mav::accumulate(c,spoof[i]);
  mini_mav::put16(spoof.data()+24,mini_mav::accumulate(c,124)); deliver(spoof); assert(state.lastRC==oldRC);
  discover(OTHER); assert(peer==PC);
  auto trailing=rcFrame(1500,1000); trailing.push_back(42); deliver(trailing); assert(state.lastRC==oldRC);
  deliver(rcFrame(65535,65535)); assert(state.lastRC==oldRC);
  // Discovery still arriving must NOT keep stale drive active.
  fakeTime+=499; discover(); assert(!state.armed && allZero()); // >500 since last RC
  deliver(rcFrame(1500,2000)); assert(!state.armed && state.inhibited && allZero());
  neutral(); deliver(command(1)); assert(state.armed);
  fakeTime+=5; deliver(rcFrame(1500,2000)); assert(!allZero());
  deliver(rcFrame(0,0)); assert(allZero() && state.inhibited && state.armed);
  fakeTime+=5; deliver(rcFrame(1500,2000)); assert(allZero());
  neutral(); fakeTime+=5; deliver(rcFrame(1500,2000)); assert(!allZero());
  // Reversal coasts both legs for at least 30 ms, then uses reverse leg only.
  fakeTime+=5; deliver(rcFrame(1500,1000)); assert(allZero());
  advance(28); assert(allZero()); advance(5); assert(duties[5]==config::MAX_PWM && duties[4]==0);
  pins[0]=LOW; loop(); assert(!state.armed && allZero());
  deliver(command(1)); assert(!state.armed); pins[0]=HIGH;
  deliver(command(1)); assert(!state.armed); neutral(); deliver(command(1)); assert(state.armed);
  deliver(command(1,400,21196)); assert(state.armed); // force command denied, never changes state
  deliver(command(0)); assert(!state.armed && allZero());
  neutral(); deliver(command(1)); assert(state.armed);
  WiFi.stations=0; loop(); assert(peer==ZERO_IP && !state.armed && allZero()); WiFi.stations=1;
  discover(); neutral(); deliver(command(1)); assert(state.armed);
  deliver({reinterpret_cast<const uint8_t *>(DISCONNECT),reinterpret_cast<const uint8_t *>(DISCONNECT)+sizeof(DISCONNECT)-1});
  assert(peer==ZERO_IP && !state.armed && allZero());
  discover(OTHER); assert(peer==OTHER && !state.armed); advance(3001); assert(peer==ZERO_IP);
  // Pure core boundary, timer wraparound, neutral dwell, extreme mixing tests.
  rover::State st; const uint32_t start=0xffffff80u;
  st.rc(1500,1500,start); st.rc(1500,1500,start+250); assert(st.arm(start+250));
  st.rc(2000,2000,start+300); int16_t l,r; st.mix(l,r); assert(l==180 && r==60);
  st.tick(start+799); assert(st.armed); st.tick(start+800); assert(!st.armed);
  for(int s=1000;s<=2000;s+=10) for(int d=1000;d<=2000;d+=10) {
    rover::State q; q.armed=true; q.inhibited=false; q.haveRC=true; q.steer=s; q.drive=d;
    q.mix(l,r); assert(abs(l)<=180 && abs(r)<=180);
  }
  // Decode unsigned MAVLink 2 with target_component truncated at trailing zero.
  auto v1=rcFrame(1500,1800); std::vector<uint8_t> v2={0xfd,17,0,0,9,255,190,70,0,0};
  v2.insert(v2.end(),v1.begin()+6,v1.begin()+23); v2.push_back(0);v2.push_back(0);
  c=0xffff;for(size_t i=1;i<v2.size()-2;++i)c=mini_mav::accumulate(c,v2[i]);
  mini_mav::put16(v2.data()+v2.size()-2,mini_mav::accumulate(c,124));
  mini_mav::Message msg; size_t used; assert(mini_mav::decode(v2.data(),v2.size(),msg,used));
  assert(msg.payload[17]==0 && mini_mav::u16(msg.payload+2)==1800);
  v2[2]=1; assert(!mini_mav::decode(v2.data(),v2.size(),msg,used));
  // Deterministic malformed-input fuzz under ASan/UBSan.
  std::mt19937 random(101); uint8_t fuzz[256];
  for(int trial=0;trial<50000;++trial) {
    size_t n=random()%256; for(size_t i=0;i<n;++i)fuzz[i]=uint8_t(random());
    mini_mav::decode(fuzz,n,msg,used);
  }
  // Outbound wire checks against independent CRC and common message layouts.
  assert(!udp.outgoing.empty());
  for(const auto &packet:udp.outgoing) {
    const auto &p=packet.data; assert(p[0]==0xfe && p[3]==1 && p[4]==1);
    const uint8_t extra=p[5]==0 ? 50 : 143;
    assert(mini_mav::u16(p.data()+p.size()-2)==referenceCRC(p.data()+1,p.size()-3,extra));
    if(p[5]==0) assert(p[1]==9 && p[10]==10 && p[11]==0 && p[14]==3);
    else assert(p[5]==77 && p[1]==3);
  }
  // End-to-end unsigned MAVLink2 dispatch, concatenated frames and timeout boundary.
  discover(); neutral(); deliver(command(1)); assert(state.armed);
  v2[2]=0; c=referenceCRC(v2.data()+1,v2.size()-3,124);
  mini_mav::put16(v2.data()+v2.size()-2,c); fakeTime+=5; deliver(v2);
  assert(state.drive==1800); advance(31); assert(!allZero());
  auto multi=rcFrame(1500,1500); auto release=rcFrame(0,0);
  multi.insert(multi.end(),release.begin(),release.end()); deliver(multi);
  assert(state.inhibited && allZero());
  // Plain force-arm request from disarmed state remains denied.
  deliver(command(0)); neutral(); deliver(command(1,400,21196)); assert(!state.armed);
  std::cout<<"PASS: actual sketch host simulation; peer locks, independent CRC, arm, release, timeout, startup output, stop button, reversal, Wi-Fi loss, wrap, mixing bounds, MAVLink2 dispatch, concatenation, force-arm rejection, 50000 malformed frames\n";
}
