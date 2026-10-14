#include <cassert>
#include <iostream>
#include <algorithm>
#include <array>
#include <vector>
#include <functional>
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <Preferences.h>
#include <esp_system.h>
#include "MeshCore.h"
#include "LinkLed.h"
#include "Pairing.h"
#define TELERC_RUNTIME_MENU 1
#define TELERC_RELAY_COUNT TEST_RELAYS
#define TELERC_NODE_INDEX 1
#define TELERC_ROLE 1
namespace base {
#include "BASE-Link.h"
}
#undef TELERC_ROLE
#define TELERC_ROLE 3
namespace rover {
#include "ROVER-Link.h"
}
#if TEST_RELAYS > 0
#undef TELERC_ROLE
#define TELERC_ROLE 2
namespace node1 {
#include "NODE1-Link.h"
}
#endif
#if TEST_RELAYS > 1
#undef TELERC_NODE_INDEX
#define TELERC_NODE_INDEX 2
namespace node2 {
#include "NODE2-Link.h"
}
#endif
struct Device {
 SX1262*r;volatile bool*irq;bool*scanning,*transmitting;std::function<void()> loop;
 size_t txRead=0;uint32_t scanEnd=0;bool cad=false;
};
std::vector<Device> devices;
struct Air {size_t src;uint32_t start,end;std::vector<uint8_t> frame;std::vector<bool> eligible,collided;};
std::vector<Air> air;
std::array<uint32_t,256> generated{};
std::vector<uint32_t> latency;
uint32_t cutStart=0,cutEnd=0;size_t cutDevice=0,uartRead=0;unsigned sequence=0;
mesh::MavParser output;
bool powered(size_t i){return !(cutStart&&i==cutDevice&&testMs>=cutStart&&testMs<cutEnd);}
bool neighbors(size_t a,size_t b){return a+1==b||b+1==a;}
void startAir(size_t i,const std::vector<uint8_t>&f){
 Air a{i,testMs,testMs+uint32_t((devices[i].r->getTimeOnAir(f.size())+999)/1000),f,
       std::vector<bool>(devices.size(),false),std::vector<bool>(devices.size(),false)};
 for(size_t j=0;j<devices.size();++j){
  a.eligible[j]=neighbors(i,j)&&powered(j)&&!*devices[j].scanning&&!*devices[j].transmitting;
  for(auto&other:air)if(neighbors(other.src,j)&&neighbors(i,j)){a.collided[j]=true;other.collided[j]=true;}
 }
 air.push_back(a);
}
void events(){
 for(size_t i=0;i<air.size();){
  auto&a=air[i];
  if(testMs<a.end){++i;continue;}
  if(powered(a.src))*devices[a.src].irq=true;
  for(size_t j=0;j<devices.size();++j)if(a.eligible[j]&&!a.collided[j]&&powered(j)&&powered(a.src)&&!*devices[j].scanning&&!*devices[j].transmitting){
   devices[j].r->rx=a.frame;*devices[j].irq=true;
  }
  air.erase(air.begin()+i);
 }
 for(size_t i=0;i<devices.size();++i){auto&d=devices[i];
  if(d.cad&&testMs>=d.scanEnd){
   d.cad=false;bool busy=false;for(auto&a:air)if(neighbors(a.src,i)&&powered(a.src))busy=true;
   d.r->scanResult=busy?RADIOLIB_LORA_DETECTED:RADIOLIB_CHANNEL_FREE;
   if(powered(i))*d.irq=true;
  }
 }
}
std::vector<uint8_t> rc(uint16_t drive){
 uint8_t f[26];base::makeRc(f,1500,uint8_t(sequence++));mesh::put16(f+8,drive);telerc::CommandMailbox::checksumRc(f);
 generated[f[2]]=testMs;return {f,f+26};
}
void pc(uint16_t drive){auto f=rc(drive);uint8_t framed[32];auto n=telerc::encodeUart(f.data(),f.size(),framed);Serial.rx.insert(Serial.rx.end(),framed,framed+n);}
void heartbeat(){
 uint8_t hb[17]={0xfe,9,0,1,1,0,0,0,0,0,10,3,0,4,3,0,0};
 uint16_t crc=0xffff;for(unsigned i=1;i<15;++i)crc=telerc::mavCrcByte(crc,hb[i]);crc=telerc::mavCrcByte(crc,50);hb[15]=uint8_t(crc);hb[16]=uint8_t(crc>>8);
 assert(mesh::telemetryClass(hb,sizeof(hb))==1);
 rover::vehicle.rx.insert(rover::vehicle.rx.end(),hb,hb+sizeof(hb));
}
void outputFrames(){
 for(;uartRead<rover::vehicle.tx.size();++uartRead)if(output.feed(rover::vehicle.tx[uartRead],testMs)){
  if(output.data[5]==70&&mesh::u16(output.data+8)>1525&&testMs<cutStart){
   uint32_t age=testMs-generated[output.data[2]];assert(age<200);latency.push_back(age);
  }
 }
}
void tick(){
 events();
 for(size_t i=0;i<devices.size();++i){auto&d=devices[i];if(!powered(i))continue;
  d.loop();
  if(*d.scanning&&!d.cad){d.cad=true;d.scanEnd=testMs+2;}
  while(d.txRead<d.r->tx.size())startAir(i,d.r->tx[d.txRead++]);
 }
 outputFrames();
}
int main(){
 devices={{&base::radio,&base::radioIRQ,&base::scanning,&base::transmitting,base::loop}};
#if TEST_RELAYS > 0
 devices.push_back({&node1::radio,&node1::radioIRQ,&node1::scanning,&node1::transmitting,node1::loop});
#endif
#if TEST_RELAYS > 1
 devices.push_back({&node2::radio,&node2::radioIRQ,&node2::scanning,&node2::transmitting,node2::loop});
#endif
 devices.push_back({&rover::radio,&rover::radioIRQ,&rover::scanning,&rover::transmitting,rover::loop});
 auto init=[](auto&cfg){cfg.khz=915000;memset(cfg.key,0x12,32);};
 init(base::cfg);init(rover::cfg);base::setup(true);rover::setup(true);
#if TEST_RELAYS > 0
 init(node1::cfg);node1::setup(true);assert(node1::settings::SELF==3);
#endif
#if TEST_RELAYS > 1
 init(node2::cfg);node2::setup(true);assert(node2::settings::SELF==4);
#endif
 cutStart=5000;cutEnd=6000;cutDevice=TEST_RELAYS?1:0;
 bool acquired=false,stopped=false,reenabled=false;uint32_t lastAccepted=0;
 for(testMs=1000;testMs<10000;++testMs){
  if(testMs==cutEnd){
   // Restore power with fresh driver state, as on an actual node reboot.
   auto&d=devices[cutDevice];d.cad=false;d.txRead=0;d.r->tx.clear();d.r->rx.clear();*d.irq=false;*d.scanning=false;*d.transmitting=false;
#if TEST_RELAYS > 0
   node1::clearQueue();node1::seen={};node1::setup(true);
#else
   base::clearQueue();base::commands={};base::seen={};Serial.rx.clear();Serial.cursor=0;base::setup(true);
#endif
  }
  if(testMs%1000==0)heartbeat();
  if(testMs%50==0)pc(testMs<2000||(testMs>=7500&&testMs<8000)?1500:1700);
  tick();
  if(testMs<cutEnd&&rover::safety.owned)lastAccepted=rover::safety.at[1];
  if(testMs>2500&&testMs<cutStart){if(rover::safety.owned!=3){std::cerr<<"failure at "<<testMs<<" rx "<<rover::rxCount<<" rejects "<<rover::rejectCount<<" stops "<<rover::stopCount<<" reason "<<unsigned(rover::lastReason)<<" radio "<<rover::radioOK<<" FC "<<rover::haveFc<<" fcAt "<<rover::fcAt<<" BASE rx "<<base::rxCount<<" tx "<<base::txCount<<" radio "<<base::radioOK<<"\n";}assert(rover::safety.owned==3);acquired=true;lastAccepted=rover::safety.at[1];}
  if(testMs>=cutStart&&testMs<7500&&testMs-lastAccepted>=500){assert(!rover::safety.owned);stopped=true;}
  if(testMs>=cutEnd&&testMs<7500)assert(!rover::safety.owned); // non-neutral recovery cannot move
  if(testMs>8500){assert(rover::safety.owned==3);reenabled=true;}
 }
 assert(acquired&&stopped&&reenabled&&rover::stopCount>=1&&latency.size()>10);
#if TEST_RELAYS > 0
 assert(node1::vehicle.tx.empty()&&!node1::safety.owned);
 // Wrong shared key blocks authenticated forwarding and causes a real stop.
 node1::cfg.key[0]^=1;
 for(;testMs<11000;++testMs){if(testMs%1000==0)heartbeat();if(testMs%50==0)pc(1700);tick();}
 assert(!rover::safety.owned&&node1::vehicle.tx.empty());
#endif
#if TEST_RELAYS > 1
 assert(node2::vehicle.tx.empty()&&!node2::safety.owned);
#endif
 // A late authenticated command cannot consume or renew an expired challenge.
 auto stale=base::makePacket(mesh::COMMAND,999);stale.sender=TEST_RELAYS?uint16_t(2+TEST_RELAYS):1;stale.hops=1;
 auto neutral=rc(1500);stale.body[0]=26;memcpy(stale.body+1,neutral.data(),26);stale.n=27;
 uint8_t wire[mesh::MAX];auto n=mesh::seal(stale,rover::cfg.key,wire);assert(n);
 rover::challenge.issue(999,testMs-mesh::timing(TEST_RELAYS+1).responseMs-1,mesh::timing(TEST_RELAYS+1).responseMs);
 size_t before=rover::vehicle.tx.size();rover::radio.rx.assign(wire,wire+n);rover::radioIRQ=true;rover::transmitting=rover::scanning=false;rover::pumpRadio();assert(rover::vehicle.tx.size()==before);
 std::sort(latency.begin(),latency.end());uint64_t total=0;for(auto x:latency)total+=x;
 std::cout<<"RELAYS="<<TEST_RELAYS<<" modeled input-to-UART ms: mean="<<double(total)/latency.size()<<" p95="<<latency[latency.size()*95/100]<<" max="<<latency.back()<<" samples="<<latency.size()<<"; actual-sketch chain, outage stop <=500ms, non-neutral recovery rejected, neutral re-enable, wrong-key rejection, replay deadline and NODE UART isolation passed\n";
}
