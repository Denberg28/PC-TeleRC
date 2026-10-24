#include <cassert>
#include <cstdio>
#include <vector>
#include "Runtime.h"
#include "fixtures.h"
using namespace mission;
Mav parse(const std::vector<uint8_t>&v){Mav m;assert(m.parse(v.data(),v.size()));return m;}
std::vector<uint8_t> encrypted(uint8_t kind,const uint8_t*body,size_t n,uint8_t mask=0){
 uint8_t out[secure::MAX];size_t size=secure::seal(out,kind,FLEET_ID,1,mask,kind==RESPONSE,body,n,roverKey(1),ROUTE_KEY);assert(size);return {out,out+size};
}
void encrypt(uint8_t kind,const uint8_t*body,size_t n,std::vector<uint8_t>&out){out=encrypted(kind,body,n);}
void deliver(std::vector<uint8_t> packet){packet[9]=secure::hops(packet[7]);assert(secure::mac(ROUTE_KEY,packet.data(),packet.size()-secure::MAC,packet.data()+packet.size()-secure::MAC));onPacket(packet.data(),packet.size());}
void resetRuntime(){
 clockMs=100;gate=Gate(1);manual={};session={};mailbox.clear();pending.n=0;transmitting=waiting=false;stopPending=false;stopCount=0;stopReason=0;lastOwned=0;
 for(auto&s:seen)s.valid=false;
 fc.tx.clear();fc.rx.clear();fc.room=4096;Serial.tx.clear();Serial.rx.clear();Serial.enabled=true;
 legacyParser.reset();usbParser.used=usbParser.total=0;replyProfile=0;selected=0;routeMask=0;misses=0;probing=false;nextPoll=0;probeAt=0;
 for(auto&s:commands)s.clear();for(auto&s:telemetry)s.clear();heartbeat.clear();fcHeartbeat.clear();
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

void request(uint8_t profile){
 pending.n=0;transmitting=false;uint8_t body[17];esp_fill_random(body,16);body[16]=profile;deliver(encrypted(SYNC,body,17));assert(pending.n&&remoteToken.active);pending.n=0;
}
void command(uint8_t profile,const std::vector<uint8_t>&frame,bool bundle=false){
 request(profile);uint8_t body[MAX_PLAIN];memcpy(body,remoteToken.token,16);body[16]=profile;body[17]=frame.size()+(bundle?1:0);
 if(bundle){body[18]=frame.size();memcpy(body+19,frame.data(),frame.size());}else memcpy(body+18,frame.data(),frame.size());
 deliver(encrypted(DATA,body,18+body[17]));
}
void manualCommand(const std::vector<uint8_t>&frame){command(unified::MANUAL,frame,true);}
void test_manual_gate(){
 Gate fcState(1);fcState.fromFc(parse(manualDisarmedHb),100);unified::Manual state;
 assert(!state.accept(parse(manualDrive),fcState,100));assert(!state.accept(parse(manualArm),fcState,100));
 assert(state.accept(parse(manualNeutral),fcState,101));assert(state.centered(101));assert(state.accept(parse(manualArm),fcState,102));
 assert(!state.accept(parse(forceArm),fcState,102));assert(!state.accept(parse(missionCount),fcState,102));assert(!state.accept(parse(servoItem),fcState,102));
 fcState.fromFc(parse(manualArmedHb),103);assert(state.accept(parse(manualDrive),fcState,104));
 assert(state.accept(parse(manualSparse),fcState,400));assert(state.at[1]==104);assert(state.expired(604));
 assert(!state.accept(parse(manualDrive),fcState,604));assert(!state.owned);assert(state.accept(parse(manualNeutral),fcState,605));
 fcState.fromFc(parse(autoArmedHb),606);assert(!state.accept(parse(manualDrive),fcState,606));assert(!state.accept(parse(manualNeutral),fcState,606));
 assert(state.accept(parse(manualRelease),fcState,5000));assert(!state.owned);
 unified::Session host;assert(host.claim(unified::MANUAL,1,100));assert(!host.claim(unified::MISSION,1,101));
 assert(!host.claim(unified::MISSION,2,500));assert(host.claim(unified::MISSION,1,1600));assert(!host.fresh(3101));
 puts("PASS manual gate: neutral-only acquisition, sparse per-axis age, MANUAL-only drive, no forced ARM, no mission/servo leak, exclusive host");
}
void test_rover_manual(){
 resetRuntime();gate.fromFc(parse(manualDisarmedHb),clockMs);
 manualCommand(manualDrive);assert(fc.tx.empty()&&!manual.owned);
 manualCommand(manualNeutral);assert(fc.tx==manualNeutral&&manual.owned==3&&manual.ready);
 fc.tx.clear();gate.fromFc(parse(manualArmedHb),clockMs);manualCommand(manualDrive);assert(fc.tx==manualDrive);
 const size_t written=fc.tx.size();clockMs+=499;manualWatchdog();assert(fc.tx.size()==written);
 ++clockMs;manualWatchdog();assert(!manual.owned&&!manual.ready&&stopCount==1&&fc.tx.size()==written+52);
 Mav stop;assert(stop.parse(fc.tx.data()+written,26)&&u16(stop.payload)==1500);assert(stop.parse(fc.tx.data()+written+26,26)&&u16(stop.payload)==0);
 fc.tx.clear();manualCommand(manualDrive);assert(fc.tx.empty());manualCommand(manualNeutral);assert(manual.owned==3);
 gate.fromFc(parse(autoArmedHb),clockMs);manualWatchdog();assert(!manual.owned&&stopCount==2);
 fc.tx.clear();manualCommand(manualNeutral);assert(fc.tx.empty());
 gate.fromFc(parse(manualArmedHb),clockMs);manualCommand(manualNeutral);assert(manual.owned);
 fc.room=0;manualCommand(manualDrive);assert(stopPending&&!manual.owned);fc.room=4096;clockMs+=20;manualWatchdog();assert(!stopPending);
 fc.tx.clear();manualCommand(manualDrive);assert(fc.tx.empty());
 manualCommand(manualNeutral);fault();assert(!manual.owned&&gate.verifiedUpload==false&&!running);
 puts("PASS rover manual runtime: real encrypted RC, 500ms stop/release, no auto-resume, AUTO rejection, UART/radio fault stop");
}
void test_rover_mission_and_switch(){
 resetRuntime();gate.fromFc(parse(disarmed),clockMs);
 command(unified::MISSION,missionCount);command(unified::MISSION,item0);command(unified::MISSION,item1);
 gate.fromFc(parse(missionAck),clockMs);assert(gate.verifiedUpload);
 size_t before=fc.tx.size();manualCommand(manualNeutral);assert(fc.tx.size()==before); // HOLD must not acquire manual.
 gate.fromFc(parse(manualDisarmedHb),clockMs);manualCommand(manualNeutral);assert(!gate.verifiedUpload&&manual.owned==3);
 before=fc.tx.size();command(unified::MISSION,startMission);assert(fc.tx.size()==before);
 manualCommand(manualRelease);assert(!manual.owned);gate.fromFc(parse(disarmed),clockMs);
 command(unified::MISSION,missionCount);command(unified::MISSION,item0);command(unified::MISSION,item1);gate.fromFc(parse(missionAck),clockMs);
 assert(gate.verifiedUpload);gate.fromFc(parse(armed),clockMs);before=fc.tx.size();command(unified::MISSION,startMission);assert(fc.tx.size()==before+startMission.size()&&gate.started);
 before=fc.tx.size();command(unified::MISSION,startMission);assert(fc.tx.size()==before);
 command(unified::MISSION,armCommand);command(unified::MISSION,rcOverride);assert(fc.tx.size()==before);
 gate.fromFc(parse(autoArmedHb),clockMs);manualCommand(manualDrive);assert(fc.tx.size()==before);
 command(unified::MISSION,holdMode);assert(fc.tx.size()==before+holdMode.size());
 puts("PASS unified mission: upload/readback gate intact, manual acquisition invalidates START, no overlap/auto-arm, one-shot START, explicit HOLD");
}
void test_rover_tokens(){
 resetRuntime();gate.fromFc(parse(manualArmedHb),clockMs);request(unified::MANUAL);
 uint8_t body[MAX_PLAIN];memcpy(body,remoteToken.token,16);body[16]=unified::MANUAL;body[17]=manualNeutral.size()+1;body[18]=manualNeutral.size();memcpy(body+19,manualNeutral.data(),manualNeutral.size());
 auto packet=encrypted(DATA,body,18+body[17]);deliver(packet);const size_t count=fc.tx.size();assert(count==manualNeutral.size());deliver(packet);assert(fc.tx.size()==count);
 deliver(encrypted(DATA,body,18+body[17]));assert(fc.tx.size()==count);
 request(unified::MISSION);memcpy(body,remoteToken.token,16);body[16]=unified::MANUAL;deliver(encrypted(DATA,body,18+body[17]));assert(fc.tx.size()==count);
 request(unified::MANUAL);memcpy(body,remoteToken.token,16);clockMs+=TOKEN_MS+1;deliver(encrypted(DATA,body,18+body[17]));assert(fc.tx.size()==count);
 puts("PASS tokens: nonce replay, new-nonce token replay, stale and cross-profile commands rejected");
}
void putUsb(const std::vector<uint8_t>&payload,bool legacy,uint8_t type=1){
 uint8_t packet[300];size_t n;
 if(legacy)n=telerc::encodeUart(payload.data(),payload.size(),packet);
 else{packet[0]=0xa5;packet[1]=0x5a;packet[2]=1;packet[3]=type;put16(packet+4,payload.size());memcpy(packet+6,payload.data(),payload.size());put16(packet+6+payload.size(),crc(packet+2,4+payload.size()));n=8+payload.size();}
 for(size_t i=0;i<n;++i)Serial.rx.push_back(packet[i]);pumpUsb();
}
void test_base_usb(){
 resetRuntime();std::vector<uint8_t>info={'T','E','L','E','R','C','_','L','O','R','A','_','G','E','T','_','V','1'};
 putUsb(info,true);assert(replyProfile==unified::MANUAL&&session.profile==unified::IDLE&&session.at==0);assert(Serial.tx[0]==0xa5&&Serial.tx[4]=='T');
 putUsb(hostHeartbeat,true);assert(session.profile==unified::MANUAL&&session.rover==1&&mailbox.hbN);
 uint32_t at=session.at;std::vector<uint8_t>query={'I','N','F','O'};Serial.tx.clear();putUsb(query,false,3);
 assert(replyProfile==unified::MISSION&&session.at==at&&session.profile==unified::MANUAL&&Serial.tx[3]==3);
 putUsb(hostHeartbeat,false);assert(session.profile==unified::MANUAL);
 clockMs+=1600;putUsb(hostHeartbeat,false);assert(session.profile==unified::MISSION&&heartbeat.n&&!mailbox.hbN);
 assert(!commands[0].n&&fc.tx.empty());
 puts("PASS base USB: legacy PC manual and TM2 mission INFO compatible, no INFO authority, exclusive handoff, old queue discarded");
}
void test_base_radio(){
 resetRuntime();assert(session.claim(unified::MANUAL,1,clockMs));selected=1;replyProfile=unified::MANUAL;
 assert(mailbox.accept(manualNeutral.data(),manualNeutral.size(),clockMs));poll();assert(pending.n&&queryProfile==unified::MANUAL);pending.n=0;waiting=true;
 uint8_t body[MAX_PLAIN]={};memcpy(body,baseQuery.token,16);esp_fill_random(body+16,16);body[32]=queryProfile;body[33]=manualDisarmedHb.size();body[42]=1;memcpy(body+50,manualDisarmedHb.data(),manualDisarmedHb.size());
 deliver(encrypted(RESPONSE,body,50+body[33],queryRoute));assert(pending.n&&pending.kind==DATA);
 uint8_t sent[MAX_PLAIN];assert(secure::open(pending.bytes,pending.n,sent,roverKey(1)));assert(sent[16]==unified::MANUAL&&sent[18]==manualNeutral.size());
 size_t queued=pending.n;deliver(encrypted(RESPONSE,body,50+body[33],queryRoute));assert(pending.n==queued); // Consumed query cannot replay a command.
 clockMs+=2000;pending.n=0;transmitting=false;waiting=false;nextPoll=0;poll();assert(!mailbox.rcN&&!mailbox.hbN&&queryProfile==unified::HEALTH);
 puts("PASS base RF: original CRC/MAV frames preserved in authenticated manual bundle; stale host cannot send cached RC");
 resetRuntime();clockMs=3100;session.claim(unified::MANUAL,1,clockMs);selected=1;
 assert(mailbox.accept(manualNeutral.data(),manualNeutral.size(),clockMs));poll();assert(probing&&queryProfile==unified::HEALTH);
 pending.n=0;waiting=true;memset(body,0,sizeof(body));memcpy(body,baseQuery.token,16);body[32]=unified::HEALTH;
 deliver(encrypted(RESPONSE,body,50,queryRoute));assert(mailbox.rcN==manualNeutral.size()&&!pending.n);
 puts("PASS idle relay health probe preserves fresh manual mailbox without transmitting it");
}
void test_node(){
 resetRuntime();uint8_t body[17]={};body[16]=unified::HEALTH;
 uint8_t mask=NODE_INDEX==1?1:2;uint8_t raw[secure::MAX],dummy[32]={1};size_t size=secure::seal(raw,SYNC,FLEET_ID,1,mask,0,body,17,dummy,ROUTE_KEY);std::vector<uint8_t> packet(raw,raw+size);onPacket(packet.data(),packet.size());assert(pending.n&&pending.bytes[9]==1);pending.n=0;
 onPacket(packet.data(),packet.size());assert(!pending.n);
 assert(unified::nodeStage(3,1,false)==0&&unified::nodeStage(3,2,false)==1);
 assert(unified::nodeStage(3,2,true)==0&&unified::nodeStage(3,1,true)==1);
 assert(unified::nodeStage(2,1,false)==-1&&unified::nodeStage(2,2,false)==0);
 puts("PASS relays: direct/N1/N2/chain route masks, role ordering and duplicate suppression");
}
int main(){setup();assert(running&&bootId);test_gate();if(ROLE!=3){test_crypto();test_manual_gate();}
 if(ROLE==2){test_rover_manual();running=true;test_rover_mission_and_switch();test_rover_tokens();}
 if(ROLE==1){test_base_usb();test_base_radio();}
 if(ROLE==3)test_node();puts("PASS actual unified runtime (host stubs; RF timing/hardware not qualified)");}
