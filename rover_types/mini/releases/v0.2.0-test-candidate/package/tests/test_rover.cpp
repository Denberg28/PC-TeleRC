#define TELERC_HOST_TEST 1
#include <cassert>
#include <iostream>
#include <random>
#include <algorithm>
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

uint16_t rv[4]={1500,1500,2000,1000};
uint64_t nextRadio=0;
void at(uint64_t time) { fakeMicros=time; fakeTime=uint32_t(time/1000); }
void pulse(uint8_t mask=15) {
  const uint64_t start=fakeMicros;
  std::vector<std::pair<uint16_t,uint8_t>> falling;
  for(uint8_t i=0;i<4;++i) if(mask&(1<<i)) {
    signalEdge(config::RX_PINS[i],HIGH); falling.emplace_back(rv[i],i);
  }
  std::sort(falling.begin(),falling.end());
  for(auto [width,index]:falling) { at(start+width); signalEdge(config::RX_PINS[index],LOW); }
  nextRadio=start+20000;
}
void advance(uint32_t ms,bool refresh=true,uint8_t mask=15) {
  const uint64_t end=fakeMicros+uint64_t(ms)*1000;
  while(fakeMicros<end) { if(refresh && fakeMicros>=nextRadio) pulse(mask); loop(); }
}
bool allZero() { for(auto &pair:config::MOTOR_PINS) for(int pin:pair) if(duties[pin]) return false; return true; }
void exclusive() { for(auto &pair:config::MOTOR_PINS) assert(!(duties[pair[0]] && duties[pair[1]])); }
void armTX() {
  rv[0]=rv[1]=1500; rv[2]=1000; rv[3]=1000;
  advance(420); rv[2]=2000; advance(40);
  assert(radioGate.selected==radio::Source::Transmitter && state.armed);
}
void permitPC() {
  rv[0]=rv[1]=1500; rv[2]=1000; rv[3]=2000;
  advance(420); rv[2]=2000; advance(40);
  assert(pcAuthority() && !state.armed);
}
void disconnectPC() {
  deliver({reinterpret_cast<const uint8_t *>(DISCONNECT),reinterpret_cast<const uint8_t *>(DISCONNECT)+sizeof(DISCONNECT)-1});
}
void neutralPC() { for(int i=0;i<8;++i) { deliver(rcFrame(1500,1500)); advance(45); } }
// Independent bit-by-bit X.25 reference, separate from firmware CRC helper.
uint16_t referenceCRC(const uint8_t *p,size_t n,uint8_t extra) {
  uint16_t crc=0xffff;
  for(size_t i=0;i<=n;++i) {
    crc ^= i<n ? p[i] : extra;
    for(int bit=0;bit<8;++bit) crc=(crc&1) ? (crc>>1)^0x8408 : crc>>1;
  }
  return crc;
}
int main() {
  setup(); assert(allZero() && !state.armed && !radioHealthy);
  discover(); deliver(command(1)); deliver(rcFrame(1500,2000)); assert(allZero() && !state.armed);
  advance(500); assert(radioHealthy && !state.armed && !radioGate.permit); // held ARM at boot
  armTX(); assert(allZero());
  rv[1]=2000; advance(50); assert(duties[4]==180 && duties[8]==180); exclusive();
  rv[0]=2000; advance(40); assert(duties[4]==180 && duties[8]==60);
  deliver(rcFrame(0,0)); deliver(command(0)); assert(state.armed && state.drive==2000);
  disconnectPC(); assert(state.armed && !allZero()); discover(); assert(state.armed);
  WiFi.stations=0; advance(50); assert(state.armed && peer==ZERO_IP && !allZero());
  WiFi.stations=1; discover();
  rv[0]=300; pulse(); loop(); assert(radioHealthy && state.armed); // one bad pulse ignored
  rv[0]=1500; advance(40); advance(145,true,7); // CH6 lost while others refresh
  assert(!radioHealthy && !state.armed && allZero());
  advance(420); assert(radioHealthy && !state.armed); armTX();
  rv[2]=1000; rv[1]=2000; advance(50); rv[2]=2000; advance(40); assert(!state.armed);
  rv[1]=1500; advance(400); assert(!state.armed); armTX(); // rejected edge is not retried
  rv[2]=1000; rv[3]=1500; advance(35); // configured RF failsafe
  assert(radioGate.selected==radio::Source::Stop && !state.armed && allZero());
  rv[2]=2000; rv[3]=1000; advance(450); assert(!state.armed); armTX();
  rv[1]=2000; advance(30); assert(!allZero()); rv[3]=2000; advance(35);
  assert(!state.armed && allZero()); advance(400); assert(!pcAuthority()); permitPC();
  discover(); deliver(command(1)); assert(!state.armed); neutralPC(); deliver(command(1)); assert(state.armed);
  deliver(rcFrame(1500,2000)); advance(10); assert(!allZero());
  auto bad=rcFrame(1500,1000); bad.back()^=1; const auto oldRC=state.lastRC;
  deliver(bad); deliver(rcFrame(1500,1000),OTHER); deliver(rcFrame(1500,1000),PC,1234);
  deliver(rcFrame(1500,1000,2)); deliver(rcFrame(65535,65535));
  auto trailing=rcFrame(1500,1000); trailing.push_back(42); deliver(trailing); assert(state.lastRC==oldRC);
  discover(OTHER); assert(peer==PC); advance(490); discover(); advance(20);
  assert(!state.armed && allZero() && pcAuthority()); // radio/discovery do not refresh PC watchdog
  deliver(rcFrame(1500,2000)); assert(!state.armed && allZero());
  neutralPC(); deliver(command(1)); assert(state.armed);
  deliver(rcFrame(1500,2000)); advance(10); deliver(rcFrame(0,0)); assert(allZero() && state.inhibited);
  deliver(rcFrame(1500,2000)); advance(10); assert(allZero());
  neutralPC(); deliver(rcFrame(1500,2000)); advance(10); assert(!allZero());
  deliver(rcFrame(1500,1000)); advance(7); assert(allZero()); advance(35);
  assert(duties[5]==180 && duties[4]==0); exclusive();
  rv[2]=1000; advance(25); assert(!state.armed && allZero()); rv[2]=2000; advance(30);
  assert(pcAuthority() && !state.armed); neutralPC(); deliver(command(1)); assert(state.armed);
  pins[0]=LOW; advance(5); assert(!state.armed && allZero()); pins[0]=HIGH;
  advance(450); deliver(command(1)); assert(!state.armed && !pcAuthority());
  permitPC(); neutralPC(); deliver(command(1)); assert(state.armed);
  WiFi.stations=0; advance(5); assert(!state.armed && allZero()); WiFi.stations=1;
  discover(); neutralPC(); deliver(command(1)); assert(state.armed);
  deliver(command(0)); neutralPC(); deliver(command(1,400,21196)); assert(!state.armed);
  deliver(command(1)); assert(state.armed); disconnectPC(); assert(!state.armed && allZero());
  advance(150,true,11); assert(!radioHealthy && !state.armed && allZero()); // missing CH5
  advance(450); assert(!pcAuthority());
  wifiReady=false; armTX(); rv[1]=1800; advance(80); assert(state.armed && !allZero()); wifiReady=true;
  rv[0]=rv[1]=1500; rv[2]=1000; at(0xfffff000ULL); nextRadio=fakeMicros; advance(400); // micros wrap
  assert(radioHealthy && radioGate.selected==radio::Source::Transmitter && !state.armed);
  rv[2]=2000; advance(35); assert(state.armed);
  rover::State st; const uint32_t start=0xffffff80u;
  st.rc(1500,1500,start); st.rc(1500,1500,start+250); assert(st.arm(start+250));
  st.rc(2000,2000,start+300); int16_t l,r; st.mix(l,r); assert(l==180 && r==60);
  st.tick(start+799); assert(st.armed); st.tick(start+800); assert(!st.armed);
  for(int s=1000;s<=2000;s+=10) for(int d=1000;d<=2000;d+=10) {
    rover::State q; q.armed=true; q.inhibited=false; q.haveRC=true; q.steer=s; q.drive=d;
    q.mix(l,r); assert(abs(l)<=180 && abs(r)<=180);
  }
  for(const auto &packet:udp.outgoing) {
    const auto &p=packet.data; assert(p[0]==0xfe && p[3]==1 && p[4]==1);
    const uint8_t extra=p[5]==0 ? 50 : 143;
    assert(mini_mav::u16(p.data()+p.size()-2)==referenceCRC(p.data()+1,p.size()-3,extra));
    if(p[5]==0) assert(p[1]==9 && p[10]==10 && p[11]==0 && p[14]==3);
  }
  auto v1=rcFrame(1500,1800); std::vector<uint8_t> v2={0xfd,17,0,0,9,255,190,70,0,0};
  v2.insert(v2.end(),v1.begin()+6,v1.begin()+23); v2.push_back(0); v2.push_back(0);
  mini_mav::put16(v2.data()+v2.size()-2,referenceCRC(v2.data()+1,v2.size()-3,124));
  mini_mav::Message msg; size_t used; assert(mini_mav::decode(v2.data(),v2.size(),msg,used));
  assert(msg.payload[17]==0); v2[2]=1; assert(!mini_mav::decode(v2.data(),v2.size(),msg,used));
  std::mt19937 random(101); uint8_t fuzz[256];
  for(int trial=0;trial<50000;++trial) {
    size_t n=random()%256; for(size_t i=0;i<n;++i)fuzz[i]=uint8_t(random()); mini_mav::decode(fuzz,n,msg,used);
  }
  std::cout<<"PASS FS-iA6: real ISR pulse capture; held-ARM lock; neutral edge arming; missing CH5/CH6; glitch rejection; STOP failsafe recovery; TX/PC handover; PC isolation; Wi-Fi isolation; PC watchdog; BOOT; reversal; timer wrap; mix bounds; independent CRC; 50000 malformed frames\n";
}
