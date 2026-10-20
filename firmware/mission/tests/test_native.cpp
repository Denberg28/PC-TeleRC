#include <cassert>
#include <cstdio>
#include <vector>
#include <fstream>
#include <string>
#include "Runtime.h"
#include "fixtures.h"
using namespace mission;
Mav parse(const std::vector<uint8_t>&v){Mav m;assert(m.parse(v.data(),v.size()));return m;}
void encrypt(uint8_t kind,const uint8_t*body,size_t n,std::vector<uint8_t>&out,uint8_t id=1){
 uint8_t p[secure::MAX];size_t k=secure::seal(p,kind,FLEET_ID,id,RELAY_COUNT,kind==RESPONSE,body,n,roverKey(id),ROUTE_KEY);assert(k);out.assign(p,p+k);
}
void feedRadio(std::vector<uint8_t>p){p[9]=RELAY_COUNT;assert(secure::mac(ROUTE_KEY,p.data(),p.size()-secure::MAC,p.data()+p.size()-secure::MAC));onPacket(p.data(),p.size());}
std::vector<Mav> batch(const uint8_t*p,size_t n){
 std::vector<Mav> result;size_t used=0;
 while(used<n){assert(n-used>=2);size_t len=p[used+1]+(p[used]==0xfd?12:8);assert(len<=n-used);Mav m;assert(m.parse(p+used,len));result.push_back(m);used+=len;}
 return result;
}
void test_gate(){
 Gate g(1);auto hb=parse(disarmed);auto arm=parse(armed);auto count=parse(missionCount);auto home=parse(item0);auto wp=parse(item1);auto ack=parse(missionAck);auto start=parse(startMission);auto hold=parse(holdMode);
 assert(!g.down(start,100));assert(g.fromFc(hb,100));assert(!g.down(parse(rcOverride),100));
 assert(!g.down(parse(armCommand),100));assert(!g.down(parse(forceArm),100));
 assert(!g.down(parse(foreignCount),100));assert(g.down(count,100));assert(g.down(home,101));
 assert(g.down(count,102)); // retransmit must retain home tracking
 assert(g.down(wp,103));assert(g.fromFc(ack,104));assert(g.verifiedUpload);
 assert(!g.down(start,105));assert(g.fromFc(arm,106));assert(g.down(start,107));assert(!g.down(start,108));
 assert(g.down(hold,108));assert(!g.down(count,108));g.tick(5000);assert(!g.verifiedUpload);assert(!g.down(start,5000));
 Gate incomplete;assert(incomplete.fromFc(hb,100));assert(incomplete.down(count,101));assert(incomplete.down(home,102));assert(incomplete.fromFc(ack,103));assert(!incomplete.verifiedUpload);
 Gate servo;servo.fromFc(hb,100);assert(servo.down(count,101));assert(!servo.down(parse(servoItem),102));assert(servo.down(parse(servoItem),102,1u<<8));
 assert(servo.down(parse(navDelay),103));assert(servo.down(parse(conditionDelay),104));assert(!servo.down(parse(badDelay),105));assert(!servo.down(parse(motorServo),106,0xffff));
 Gate reboot;reboot.fromFc(hb,100);reboot.down(count,101);reboot.down(home,102);reboot.down(wp,103);reboot.fromFc(ack,104);assert(reboot.verifiedUpload);
 reboot.fromFc(parse(position1000),105);reboot.fromFc(parse(position100),106);assert(!reboot.verifiedUpload);
 auto invalid=disarmed;invalid[5]^=1;Mav m;assert(!m.parse(invalid.data(),invalid.size()));
 for(size_t n=0;n<disarmed.size();++n)assert(!m.parse(disarmed.data(),n));
 auto signature=disarmed;signature[2]=1;assert(!m.parse(signature.data(),signature.size()));
 MavStream stream;Mav out;for(auto b:disarmed)stream.feed(b,1,out);assert(out.id==0);
 stream.feed(0xfd,2,out);for(auto b:disarmed)stream.feed(b,200,out);assert(out.id==0);
 puts("PASS gate: addressing, CRC, no RC/arm/force-arm, complete upload, no auto-start, single start, stale/reboot, servo opt-in");
}
void test_crypto(){
 uint8_t body[mission::MAX_PLAIN]={};esp_fill_random(body,sizeof(body));std::vector<uint8_t>p;encrypt(DATA,body,sizeof(body),p);
 assert(secure::hopValid(p.data(),p.size(),ROUTE_KEY,FLEET_ID,RELAY_COUNT));uint8_t out[mission::MAX_PLAIN];assert(secure::open(p.data(),p.size(),out,roverKey(1)));assert(equal(out,body,sizeof(body)));
 uint8_t wrong[32]={};assert(!secure::open(p.data(),p.size(),out,wrong));
 for(size_t i=0;i<p.size();++i){auto q=p;q[i]^=1;assert(!secure::hopValid(q.data(),q.size(),ROUTE_KEY,FLEET_ID,RELAY_COUNT));}
 auto forged=p;forged[secure::HEAD+secure::NONCE+20]^=1;assert(secure::mac(ROUTE_KEY,forged.data(),forged.size()-secure::MAC,forged.data()+forged.size()-secure::MAC));assert(!secure::open(forged.data(),forged.size(),out,roverKey(1)));
 assert(!secure::hopValid(p.data(),p.size(),ROUTE_KEY,FLEET_ID+1,RELAY_COUNT));
 Challenge c;uint8_t token[16]={1},other[16]={2};c.issue(token,100);assert(!c.consume(other,101));assert(c.consume(token,102));assert(!c.consume(token,103));c.issue(token,0);assert(!c.consume(token,TOKEN_MS+1));
 c.issue(token,0xfffffff0);assert(c.consume(token,5));
 for(size_t n=0;n<p.size();++n)assert(!secure::hopValid(p.data(),n,ROUTE_KEY,FLEET_ID,RELAY_COUNT));
 puts("PASS crypto: AES-GCM roundtrip, wrong key, every-byte tamper, relay-key compromise isolation, fleet ID, lengths, token replay/expiry/wrap");
}
void test_usb(){
 HostStream s;std::vector<uint8_t>p(disarmed.size()+8);p[0]=0xa5;p[1]=0x5a;p[2]=1;p[3]=1;put16(p.data()+4,disarmed.size());memcpy(p.data()+6,disarmed.data(),disarmed.size());put16(p.data()+p.size()-2,crc(p.data()+2,p.size()-4));
 unsigned accepted=0;for(auto b:p)accepted+=s.feed(b,0);assert(accepted==1);
 p.back()^=1;for(auto b:p)assert(!s.feed(b,1));
 puts("PASS USB framing and corrupt frame rejection");
}
void test_rover(){
 clockMs=100;gate=Gate(1);gate.fromFc(parse(disarmed),100);pending.n=0;transmitting=false;
 uint8_t sync[16]={};esp_fill_random(sync,16);std::vector<uint8_t>p;encrypt(SYNC,sync,16,p);
 if(RELAY_COUNT){onPacket(p.data(),p.size());assert(!pending.n);} // Overheard early stage must not poison dedup.
 feedRadio(p);assert(pending.n);assert(remoteToken.active);pending.n=0;
 uint8_t down[MAX_PLAIN];memcpy(down,remoteToken.token,16);down[16]=missionCount.size();memcpy(down+17,missionCount.data(),missionCount.size());
 encrypt(DATA,down,17+down[16],p);auto once=p;feedRadio(p);assert(gate.uploading);size_t written=fc.tx.size();assert(written==missionCount.size());feedRadio(once);assert(fc.tx.size()==written);
 // A new nonce cannot reuse a consumed challenge either.
 encrypt(DATA,down,17+down[16],p);feedRadio(p);assert(fc.tx.size()==written);
 // No controller heartbeat is generated while the host is absent.
 size_t before=fc.tx.size();clockMs=5000;for(unsigned i=0;i<20;++i)loop();assert(fc.tx.size()==before);
 // A heartbeat every long multi-hop poll cannot starve mission ACK/request.
 pending.n=0;transmitting=false;servedHeartbeat=false;
 for(auto&s:telemetry)s.clear();
 for(unsigned turn=0;turn<2;++turn){
  clockMs=6000+turn*1500;fcHeartbeat.set(disarmed.data(),disarmed.size(),clockMs);
  telemetry[0].set(missionAck.data(),missionAck.size(),clockMs);
  esp_fill_random(sync,16);encrypt(SYNC,sync,16,p);feedRadio(p);assert(pending.n);
  uint8_t plain[MAX_PLAIN];assert(secure::open(pending.bytes,pending.n,plain,roverKey(1)));
  auto chosen=batch(plain+33,plain[32]);assert(chosen.size()==2&&chosen[0].id==0&&chosen[1].id==47);pending.n=0;
 }
 // Refresh all navigation streams every turn. Rotating slots must still serve
 // position/current/reached instead of repeatedly choosing only GPS.
 for(auto&s:telemetry)s.clear();navCursor=0;
 bool got[4]={};const std::vector<uint8_t>*nav[]={&gps,&position1000,&current,&reached};
 for(unsigned turn=0;turn<2;++turn){
  clockMs=10000+turn*1500;pending.n=0;transmitting=false;
  fcHeartbeat.set(disarmed.data(),disarmed.size(),clockMs);
  for(unsigned i=0;i<4;++i)telemetry[4+i].set(nav[i]->data(),nav[i]->size(),clockMs);
  esp_fill_random(sync,16);encrypt(SYNC,sync,16,p);feedRadio(p);
  uint8_t plain[MAX_PLAIN];assert(pending.n&&secure::open(pending.bytes,pending.n,plain,roverKey(1)));
  auto selected=batch(plain+33,plain[32]);assert(selected.size()<=4&&plain[32]<=100&&selected[0].id==0);
  for(const auto&m:selected){if(m.id==24)got[0]=true;if(m.id==33)got[1]=true;if(m.id==42)got[2]=true;if(m.id==46)got[3]=true;}
 }
 for(bool delivered:got)assert(delivered);pending.n=0;
 puts("PASS rover runtime: encrypted command forwarding once, duplicate/new-nonce replay denied, no synthetic GCS heartbeat");
 puts("PASS multi-hop batching: heartbeat and mission reply share each bounded response");
}
void test_base(){
 servedHostHeartbeat=false;
 selected=1;clockMs=100;hostAt=100;running=true;pending.n=0;waiting=false;transmitting=false;nextPoll=0;
 commands[0].set(startMission.data(),startMission.size(),100);heartbeat.set(disarmed.data(),disarmed.size(),100);poll();assert(pending.n);pending.n=0;
 uint8_t body[MAX_PLAIN]={};memcpy(body,baseQuery.token,16);esp_fill_random(body+16,16);body[32]=disarmed.size();memcpy(body+33,disarmed.data(),disarmed.size());std::vector<uint8_t>p;encrypt(RESPONSE,body,33+body[32],p);waiting=true;
 if(RELAY_COUNT){onPacket(p.data(),p.size());assert(!pending.n);} // Overlap between direct and relayed RF reception.
 feedRadio(p);assert(pending.n&&pending.kind==DATA);
 uint8_t sent[MAX_PLAIN];assert(secure::open(pending.bytes,pending.n,sent,roverKey(1)));Mav outgoing;assert(outgoing.parse(sent+17,sent[16]));assert(outgoing.id==0&&commands[0].n);pending.n=0;
 // A previous response cannot acquire a fresh query or queue a start again.
 feedRadio(p);assert(!pending.n);
 clockMs=5000;commands[0].set(startMission.data(),startMission.size(),100);waiting=false;poll();assert(!commands[0].n&&!pending.n);
 // An incoming HOLD purges unsent mission/START work and pending DATA.
 std::vector<uint8_t>stop(holdMode.size()+8);stop[0]=0xa5;stop[1]=0x5a;stop[2]=1;stop[3]=1;put16(stop.data()+4,holdMode.size());memcpy(stop.data()+6,holdMode.data(),holdMode.size());put16(stop.data()+stop.size()-2,crc(stop.data()+2,stop.size()-4));
 commands[1].set(startMission.data(),startMission.size(),clockMs);pending.n=1;pending.kind=DATA;transmitting=false;
 for(auto b:stop)Serial.rx.push_back(b);pumpUsb();
 assert(!pending.n&&!commands[1].n);Mav held;assert(held.parse(commands[0].data,commands[0].n)&&holdFrame(held,1));
 // Capability queries do not select a rover or refresh host authority.
 uint8_t info[12]={0xa5,0x5a,1,3,4,0,'I','N','F','O'};put16(info+10,crc(info+2,8));
 uint32_t previousHost=hostAt;for(auto b:info)Serial.rx.push_back(b);Serial.tx.clear();pumpUsb();
 assert(hostAt==previousHost&&Serial.tx.size()>8&&Serial.tx[3]==3);
 puts("PASS base runtime: actual host heartbeat fairness, no replay, stale command expiry, version handshake without authority");
}
void test_node(){
 clockMs=100;pending.n=0;transmitting=false;uint8_t body[16]={};uint8_t k[32]={1},packet[secure::MAX];
 size_t n=secure::seal(packet,SYNC,FLEET_ID,1,RELAY_COUNT,0,body,16,k,ROUTE_KEY);packet[9]=NODE_INDEX-1;secure::mac(ROUTE_KEY,packet,n-secure::MAC,packet+n-secure::MAC);
 onPacket(packet,n);assert(pending.n==n&&pending.bytes[9]==NODE_INDEX);assert(secure::hopValid(pending.bytes,n,ROUTE_KEY,FLEET_ID,RELAY_COUNT));
 pending.n=0;onPacket(packet,n);assert(!pending.n);puts("PASS relay runtime: fixed directional stage, hop authentication, duplicate suppression, no rover key");
}
int main(){
 setup();assert(running);test_gate();
 if(ROLE!=3)test_crypto();test_usb();
 if(ROLE==1)test_base();if(ROLE==2)test_rover();if(ROLE==3)test_node();
 puts("ALL NATIVE CHECKS PASSED (HOST STUBS, NOT BOARD VALIDATION)");
}
