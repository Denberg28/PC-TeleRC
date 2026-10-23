#include <cassert>
#include <cstdio>
#include <vector>
#include <cstring>
#include "TestRole.h"
#include "Runtime.h"
#include "fixtures.h"
using namespace mission;
Mav parse(const std::vector<uint8_t>&v){Mav m;assert(m.parse(v.data(),v.size()));return m;}
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
std::vector<uint8_t> packet(uint8_t kind,uint8_t id,const uint8_t*body,size_t len,const uint8_t*route=nullptr,uint8_t count=0){
 uint8_t key[32],out[secure::MAX];assert(secure::derive(testRoot,FLEET_ID,id,key));
 size_t n=secure::seal(out,kind,FLEET_ID,id,route,count,body,len,key,ROUTE_KEY);assert(n);return {out,out+n};
}
void remac(std::vector<uint8_t>&p){assert(secure::mac(ROUTE_KEY,p.data(),p.size()-secure::MAC,p.data()+p.size()-secure::MAC));}
void crypto_test(){
 uint8_t route[]={17,200,4,99},body[MAX_PLAIN],plain[MAX_PLAIN];esp_fill_random(body,sizeof(body));unsigned routes=0;
 for(uint8_t id=1;id<=20;++id)for(unsigned hops=0;hops<=4;++hops){
  uint8_t key[32],other[32];assert(secure::derive(testRoot,FLEET_ID,id,key));assert(secure::derive(testRoot,FLEET_ID,id==20?1:id+1,other));assert(!equal(key,other,32));
  auto q=packet(SYNC,id,body,16);
  for(unsigned i=0;i<hops;++i){assert(secure::forNode(q.data(),route[i]));assert(secure::advance(q.data(),q.size(),route[i],ROUTE_KEY));assert(!secure::forNode(q.data(),route[i]));}
  assert(q[7]==hops&&secure::hopValid(q.data(),q.size(),ROUTE_KEY,FLEET_ID));assert(secure::open(q.data(),q.size(),plain,key)&&equal(plain,body,16));
  auto reply=packet(RESPONSE,id,body,sizeof(body),route,hops);
  for(int i=int(hops)-1;i>=0;--i)assert(secure::advance(reply.data(),reply.size(),route[i],ROUTE_KEY));
  assert(secure::atBase(reply.data())&&secure::hopValid(reply.data(),reply.size(),ROUTE_KEY,FLEET_ID));
  assert(secure::open(reply.data(),reply.size(),plain,key)&&equal(body,plain,sizeof(body)));
  assert(!secure::open(reply.data(),reply.size(),plain,other));
  auto data=packet(DATA,id,body,sizeof(body),route,hops);
  for(unsigned i=0;i<hops;++i)assert(secure::advance(data.data(),data.size(),route[i],ROUTE_KEY));
  assert(secure::atRover(data.data())&&secure::open(data.data(),data.size(),plain,key)&&equal(plain,body,sizeof(body)));
  for(size_t i=0;i<data.size();++i){auto corrupt=data;corrupt[i]^=1;assert(!secure::hopValid(corrupt.data(),corrupt.size(),ROUTE_KEY,FLEET_ID));}
  auto forged=data;forged[secure::HEAD+secure::NONCE]^=1;remac(forged);assert(!secure::open(forged.data(),forged.size(),plain,key));
  if(hops){forged=data;forged[14]=18;remac(forged);assert(!secure::open(forged.data(),forged.size(),plain,key));}
  ++routes;
 }
 // Routing key alone cannot create a mission endpoint packet.
 auto fake=packet(DATA,1,body,16);assert(!secure::open(fake.data(),fake.size(),plain,ROUTE_KEY));
 assert(!secure::derive(testRoot,FLEET_ID,0,plain));assert(!secure::derive(testRoot,FLEET_ID,21,plain));
 // Random noise and every truncated boundary must fail closed.
 for(size_t i=0;i<fake.size();++i)assert(!secure::hopValid(fake.data(),i,ROUTE_KEY,FLEET_ID));
 printf("PASS TF2: %u rover/route combinations, every-byte tampering, endpoint isolation, AEAD route binding\n",routes);
}
std::vector<uint8_t> retarget(const std::vector<uint8_t>&original,uint8_t id,bool fromFc){
 auto p=original;auto m=parse(p);unsigned head=p[0]==0xfd?10:6;
 if(fromFc)p[p[0]==0xfd?5:3]=id;
 else if(m.id==44)p[head+2]=id;
 uint16_t c=acc(crc(p.data()+1,head-1+p[1]),Mav::extra(m.id));put16(p.data()+head+p[1],c);assert(parse(p).sys==(fromFc?id:255));return p;
}
void resetRf(){pending.n=0;transmitting=scanning=waiting=false;irq=false;running=true;clockMs=100;for(auto&s:seen)s.valid=false;clearCommands();}
void usbFeed(uint8_t id,uint8_t kind,const uint8_t*body,size_t n){
 std::vector<uint8_t>p(n+8);p[0]=0xa5;p[1]=0x5a;p[2]=id;p[3]=kind;put16(p.data()+4,n);memcpy(p.data()+6,body,n);put16(p.data()+6+n,crc(p.data()+2,n+4));
 for(auto b:p)Serial.rx.push_back(b);pumpUsb();
}
void rover_test(){
 resetRf();gate=Gate(ROVER_ID);auto hb=retarget(disarmed,ROVER_ID,true);assert(gate.fromFc(parse(hb),clockMs));
 auto count=retarget(missionCount,ROVER_ID,false);uint8_t route[]={17,4,99,200},sync[16];esp_fill_random(sync,16);
 auto q=packet(SYNC,ROVER_ID,sync,16);
 for(unsigned i=0;i<4;++i)assert(secure::advance(q.data(),q.size(),route[i],ROUTE_KEY));
 fcHeartbeat.set(hb.data(),hb.size(),clockMs);auto ack=retarget(missionAck,ROVER_ID,true);telemetry[0].set(ack.data(),ack.size(),clockMs);
 onPacket(q.data(),q.size());assert(pending.n&&remoteToken.active&&pathCount==4);
 uint8_t key[32],plain[MAX_PLAIN];assert(secure::derive(testRoot,FLEET_ID,ROVER_ID,key));assert(secure::open(pending.bytes,pending.n,plain,key));assert(plain[40]==hb.size()+ack.size());assert(fleet::readId(plain+32)==ESP.getEfuseMac());pending.n=0;
 uint8_t down[MAX_PLAIN];memcpy(down,remoteToken.token,16);down[16]=count.size();memcpy(down+17,count.data(),count.size());
 auto d=packet(DATA,ROVER_ID,down,17+count.size(),route,4);for(auto id:route)assert(secure::advance(d.data(),d.size(),id,ROUTE_KEY));
 fc.tx.clear();onPacket(d.data(),d.size());assert(gate.uploading&&fc.tx.size()==count.size());auto written=fc.tx.size();onPacket(d.data(),d.size());assert(fc.tx.size()==written);
 auto replay=packet(DATA,ROVER_ID,down,17+count.size(),route,4);for(auto id:route)assert(secure::advance(replay.data(),replay.size(),id,ROUTE_KEY));onPacket(replay.data(),replay.size());assert(fc.tx.size()==written);
 clockMs+=5000;for(unsigned i=0;i<20;++i)loop();assert(fc.tx.size()==written); // No synthetic heartbeat.
 gate.verifiedUpload=true;fault();assert(!gate.verifiedUpload&&!remoteToken.active&&!pending.n);clockMs=recoveryAt;loop();assert(running&&!gate.verifiedUpload&&fc.tx.size()==written);
 puts("PASS actual rover Runtime: editable ID, 4-node discovery, batched real heartbeat, once-only UART, replay/stale rejection, RF recovery without restart");
}
void base_test(){
 resetRf();owner=selected=0;hostAt=0;nextPoll=0;
 const uint8_t watching[]="WATCH:20,3";usbFeed(1,4,watching,sizeof(watching)-1);assert(watchCount==2&&watch[0]==20&&owner==0&&hostAt==0);
 poll();assert(pending.n&&selected==20&&pending.bytes[6]==20);pending.n=0;waiting=true;
 uint8_t body[MAX_PLAIN]={};memcpy(body,baseQuery.token,16);esp_fill_random(body+16,16);fleet::writeId(body+32,1234);auto hb=retarget(disarmed,20,true);body[40]=hb.size();memcpy(body+41,hb.data(),hb.size());
 auto response=packet(RESPONSE,20,body,41+hb.size());Serial.tx.clear();onPacket(response.data(),response.size());assert(!waiting&&Serial.tx.size()>8&&Serial.tx[2]==20&&!pending.n);
 // A second authenticated device with the same ID is detected even after the first consumed the query.
 fleet::writeId(body+32,5678);response=packet(RESPONSE,20,body,41+hb.size());onPacket(response.data(),response.size());assert(roverIdentity[19].conflict&&!pending.n);
 auto before=hostAt;const uint8_t info[]="INFO";usbFeed(1,3,info,4);assert(hostAt==before&&owner==0);
 auto gcs=hostHeartbeat;usbFeed(3,1,gcs.data(),gcs.size());assert(owner==3&&selected==3&&heartbeat.n);
 usbFeed(4,1,gcs.data(),gcs.size());assert(owner==3);clockMs+=5001;pending.n=0;usbFeed(4,1,gcs.data(),gcs.size());assert(owner==4&&selected==4);
 clockMs+=HOST_MS+1;clearCommands();assert(!heartbeat.n);poll();assert(!commands[0].n);
 const uint8_t invalid[]="WATCH:1,1";assert(!setWatch(invalid,sizeof(invalid)-1)&&watchCount==2);
 const uint8_t huge[]="WATCH:9999999999999999999999999999999999";assert(!setWatch(huge,sizeof(huge)-1));
 resetRf();owner=selected=1;hostAt=clockMs;usbFeed(1,1,startMission.data(),startMission.size());assert(commands[0].n);usbFeed(1,1,holdMode.data(),holdMode.size());assert(!commands[1].n);assert(holdFrame(parse({commands[0].data,commands[0].data+commands[0].n}),1));
 fault();assert(!commands[0].n&&!remoteToken.active&&!baseQuery.active);clockMs=recoveryAt;loop();assert(running&&!commands[0].n);
 puts("PASS actual base Runtime: unlisted ID20 without base rebuild, read-only WATCH, duplicate-ID quarantine, exclusive writer, HOLD priority, recovery discards commands");
}
void node_test(){
 resetRf();uint8_t sync[16]={};auto p=packet(SYNC,20,sync,16);onPacket(p.data(),p.size());assert(pending.n&&pending.bytes[7]==1&&pending.bytes[14]==NODE_ID);pending.n=0;
 onPacket(p.data(),p.size());assert(!pending.n); // Deduplicated flood.
 nextHello=clockMs;nodeHello();assert(pending.n&&pending.kind==secure::HELLO);uint8_t plain[MAX_PLAIN];assert(secure::open(pending.bytes,pending.n,plain,ROUTE_KEY));assert(plain[24]==NODE_ID);pending.n=0;
 uint8_t ack[MAX_PLAIN];memcpy(ack,plain,25);ack[25]=1;uint8_t route[]={NODE_ID},out[secure::MAX];size_t n=secure::seal(out,secure::HELLO_ACK,FLEET_ID,0,route,1,ack,26,ROUTE_KEY,ROUTE_KEY);
 onPacket(out,n);assert(nodeReady);onPacket(out,n);assert(nodeReady); // Token consumed; no new authorization.
 fault();assert(!nodeReady);clockMs=recoveryAt;loop();assert(running&&!nodeReady);
 puts("PASS actual node Runtime: arbitrary ID discovery, replay suppression, idle HELLO/ACK READY, automatic RF recovery");
}
void identity_test(){
 fleet::Identity identity;assert(identity.observe(123,100));assert(identity.observe(123,101));assert(!identity.observe(456,102)&&identity.conflict);assert(!identity.observe(123,103));assert(identity.observe(456,90200)&&!identity.conflict);
 Challenge c;uint8_t query[16]={};c.issue(query,0xfffffff0);assert(c.consume(query,4));assert(!c.consume(query,5));c.issue(query,100);assert(!c.consume(query,100+TOKEN_MS+1));
 puts("PASS duplicate identity quarantine, freshness wraparound and one-use challenge");
}
void radio_test(){
 resetRf();uint8_t bytes[20]={};assert(queuePacket(bytes,sizeof(bytes),SYNC,0));pumpRadio();assert(scanning);radio.cad=RADIOLIB_LORA_DETECTED;irq=true;pumpRadio();assert(!scanning&&pending.n&&!transmitting);
 clockMs=pending.due;radio.cad=RADIOLIB_CHANNEL_FREE;pumpRadio();assert(scanning);irq=true;pumpRadio();assert(transmitting&&!pending.n);
 // A missed CPU edge with real TX_DONE recovers RX; an RF timeout clears authority.
 irq=false;clockMs=txAt+txLimit+1;pumpRadio();assert(running&&!transmitting);
 assert(queuePacket(bytes,sizeof(bytes),SYNC,0));pumpRadio();irq=true;pumpRadio();assert(transmitting);radio.irqFlags=0;clockMs=txAt+txLimit+1;pumpRadio();assert(!running&&!pending.n&&!remoteToken.active);radio.irqFlags=1;clockMs=recoveryAt;loop();assert(running);
 resetRf();assert(queuePacket(bytes,sizeof(bytes),SYNC,0));clockMs+=501;pumpRadio();assert(!pending.n&&!transmitting);
 puts("PASS CAD busy backoff, queue expiry, TX_DONE polling and RF timeout recovery without command replay");
}
int main(){
 setup();assert(running);test_gate();crypto_test();identity_test();radio_test();
 if(ROLE==1)base_test();if(ROLE==2)rover_test();if(ROLE==3)node_test();
 return 0;
}
