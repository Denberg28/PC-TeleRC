#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <bootloader_random.h>
#include "Config.h"
#include "Crypto.h"
#include "TinyOled.h"
#include "TeleRCWire.h"
#include "Manual.h"

#if defined(ARDUINO_ARCH_ESP32)
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "TeleRC Unified requires the ESP32-S3 LilyGO SX1262 board profile"
#endif
#if !ARDUINO_USB_CDC_ON_BOOT || !ARDUINO_USB_MODE
#error "Enable USB CDC On Boot and Hardware CDC/JTAG USB mode"
#endif
#endif

static_assert(ROLE>=1&&ROLE<=3,"Invalid role");
static_assert(RELAY_COUNT==mesh::MAX_HOPS,"All roles use the same bounded routing capacity");
static_assert(ROLE!=3||(NODE_ID>=1&&NODE_ID<=mesh::MAX_NODE),"Node ID must be 1..200");
static_assert(ROVER_ID>=1&&ROVER_ID<=20,"Rover ID must be 1..20");
static_assert(POWER_DBM>=2&&POWER_DBM<=17,"Power 2..17 dBm only");
SX1262 radio=new Module(7,33,8,34);
HardwareSerial fc(1);
telerc::TinyOled oled;
mission::Gate gate(ROVER_ID);
unified::Manual manual;unified::Session session;telerc::UartParser legacyParser;telerc::CommandMailbox mailbox;
uint8_t replyProfile=unified::IDLE,remoteProfile=0,queryProfile=0,misses=0;
mesh::Route remoteRoute,queryRoute;mesh::Link linkState;bool haveRemoteRoute=false,discovering=false;
uint32_t transaction=0,discoveryAt=0,nodeDiscoveryAt=0;bool haveDiscovery=false,nodeDiscovered=false;
bool authorizedRadio=false;uint32_t radioRetryAt=0,rxRearmAt=0;
uint32_t nodeReplyAt=0,probeAt=0,bootId=0,stopCount=0,stopTryAt=0;uint8_t stopReason=0,lastOwned=0;bool stopPending=false;
void stopControl(uint8_t reason);void tryStop();void acceptManual(const uint8_t*,size_t);void manualWatchdog();
mission::MavStream fcParser;mission::HostStream usbParser;
mission::Frame commands[4],heartbeat,telemetry[8],fcHeartbeat;
mission::Challenge remoteToken,baseQuery;
uint8_t selected=0;
uint32_t hostAt=0,lastPoll=0,nextPoll=0,txAt=0,txLimit=0,displayAt=0,wakeAt=0,diagAt=0;
bool running=false,transmitting=false,waiting=false,stopped=false;
bool servedHeartbeat=false;
bool servedHostHeartbeat=false;
unsigned criticalCursor=0,navCursor=0;
volatile bool irq=false;
uint32_t rxCount=0,txCount=0,rejectCount=0,dropCount=0;
struct Pending {uint8_t bytes[secure::MAX]={};size_t n=0;uint32_t due=0,at=0;uint8_t kind=0;} pending;
struct Seen {uint8_t nonce[12]={};uint32_t at=0;bool valid=false;} seen[64];unsigned seenIndex=0;
void IRAM_ATTR radioInterrupt(){irq=true;}
const uint8_t* roverKey(uint8_t id){for(const auto&v:ROVERS)if(v.id==id)return v.key;return nullptr;}
bool keySet(const uint8_t*p){uint8_t any=0;for(unsigned i=0;i<32;++i)any|=p[i];return any;}
bool holdFrame(const mission::Mav&m,uint8_t id){
 const auto*p=m.payload;
 return m.id==76&&m.sys==255&&m.comp==190&&p[30]==id&&p[31]==1&&mission::u16(p+28)==176&&mission::real(p)==1&&mission::real(p+4)==4;
}
void clearCommands(){for(auto&s:commands)s.clear();heartbeat.clear();mailbox.clear();remoteToken.active=false;}
void usbOut(uint8_t id,uint8_t type,const uint8_t*p,size_t n){
 if(!n||n>mission::MAX_MAV)return;uint8_t out[mission::MAX_MAV+8];size_t size=0;
 if(replyProfile==unified::MANUAL){size=telerc::encodeUart(p,n,out);}
 else {out[0]=0xa5;out[1]=0x5a;out[2]=id;out[3]=type;mission::put16(out+4,n);memcpy(out+6,p,n);mission::put16(out+6+n,mission::crc(out+2,n+4));size=n+8;}
 if(Serial&&Serial.availableForWrite()>=int(size))Serial.write(out,size);else ++dropCount;
}
void status(const char*msg){if(ROLE==1)usbOut(selected?selected:1,2,reinterpret_cast<const uint8_t*>(msg),strlen(msg));}
void fault(){running=false;stopped=true;transmitting=waiting=false;pending.n=0;clearCommands();linkState.clear();baseQuery.active=false;gate.invalidate();stopControl(6);radio.standby();radioRetryAt=millis();status("RF fault; retry pending; control released");}
bool receiveMode(){irq=false;int s=radio.startReceive();if(s!=RADIOLIB_ERR_NONE){fault();return false;}rxRearmAt=millis();return true;}
bool queuePacket(const uint8_t*p,size_t n,uint8_t kind,uint32_t delayMs=2){
 if(pending.n||transmitting||n>sizeof(pending.bytes)){++dropCount;return false;}
 memcpy(pending.bytes,p,n);pending.n=n;pending.kind=kind;pending.at=millis();pending.due=millis()+delayMs;return true;
}
bool makePacket(uint8_t kind,uint8_t id,const uint8_t*body,size_t n,const mesh::Route&path,bool discover=false,uint32_t txid=0){
 const auto*key=roverKey(id);if(!key)return false;uint8_t packet[secure::MAX];
 size_t size=secure::seal(packet,kind,FLEET_ID,id,path,kind==mission::RESPONSE?1:0,body,n,key,ROUTE_KEY,discover,txid);
 return size&&queuePacket(packet,size,kind);
}
bool duplicate(const uint8_t*p,uint32_t now){
 for(const auto&s:seen)if(s.valid&&uint32_t(now-s.at)<10000&&mission::equal(s.nonce,p+secure::HEAD,12))return true;
 auto&s=seen[seenIndex++%64];memcpy(s.nonce,p+secure::HEAD,12);s.at=now;s.valid=true;return false;
}
bool takeFrame(mission::Frame*slots,size_t count,mission::Frame&out,uint32_t now,uint32_t ttl){
 for(size_t i=0;i<count;++i){auto&s=slots[i];if(!s.n)continue;if(!s.fresh(now,ttl)){s.clear();++dropCount;continue;}out=s;s.clear();return true;}return false;
}
bool pushFrame(mission::Frame*slots,size_t count,const uint8_t*p,size_t n,uint32_t now){
 for(size_t i=0;i<count;++i)if(!slots[i].n)return slots[i].set(p,n,now);
 ++dropCount;return false;
}
void onPacket(uint8_t*p,size_t n){
 uint32_t now=millis();
 if(!secure::hopValid(p,n,ROUTE_KEY,FLEET_ID)){++rejectCount;return;}
 if(ROLE==3){
  // A response cancels the same outstanding discovery, even off its path.
  if(p[3]==mission::RESPONSE&&pending.n&&secure::discovery(pending.bytes)&&mission::u32(p+16)==mission::u32(pending.bytes+16))pending.n=0;
  if(secure::discovery(p)){
   if(secure::route(p).contains(NODE_ID)||p[7]>=mesh::MAX_HOPS||duplicate(p,now)||
      (nodeDiscovered&&uint32_t(now-nodeDiscoveryAt)<mesh::NODE_DISCOVERY_MS)){++rejectCount;return;}
   if(!secure::extend(p,n,NODE_ID,ROUTE_KEY)||!queuePacket(p,n,p[3],mesh::contention(p+secure::HEAD,NODE_ID))){++dropCount;return;}
   nodeDiscovered=true;nodeDiscoveryAt=now;++rxCount;return;
  }
  int expected=secure::route(p).stage(NODE_ID,p[8]!=0);
  if(expected<0||p[9]!=unsigned(expected)||duplicate(p,now)){++rejectCount;return;}
  ++rxCount;if(!secure::advance(p,n,ROUTE_KEY)||!queuePacket(p,n,p[3],2)){++dropCount;}else if(p[8])nodeReplyAt=now;return;
 }
 uint8_t id=p[6];
 if(p[9]!=p[7]||(ROLE==1?(id!=selected||p[8]!=1||p[3]!=mission::RESPONSE):(id!=ROVER_ID||p[8]!=0||p[3]==mission::RESPONSE))){++rejectCount;return;}
 if(duplicate(p,now)){++rejectCount;return;}
 const uint8_t*key=roverKey(id);uint8_t body[mission::MAX_PLAIN];
 if(!key||!secure::open(p,n,body,key)){++rejectCount;return;}
 size_t len=mission::u16(p+10);++rxCount;
 if(ROLE==1){
  if(!waiting||len<50||(!discovering&&secure::route(p)!=queryRoute)||mission::u32(p+16)!=transaction||body[32]!=queryProfile||!baseQuery.consume(body,now)){++rejectCount;return;}
  size_t mavLen=body[33];if(len!=50+mavLen||mavLen>mission::MAX_MAV){++rejectCount;return;}
  size_t cursor=0;mission::Mav frames[4];unsigned count=0;
  while(cursor<mavLen&&count<4){auto*q=body+50+cursor;if(mavLen-cursor<2||(q[0]!=0xfe&&q[0]!=0xfd)){++rejectCount;return;}
   size_t frameLen=q[1]+(q[0]==0xfd?12:8);if(frameLen>mavLen-cursor||!frames[count].parse(q,frameLen)||frames[count].sys!=selected||frames[count].comp!=1){++rejectCount;return;}cursor+=frameLen;++count;}
  if(cursor!=mavLen)return;
  const uint32_t rtt=now-baseQuery.at;
  waiting=false;misses=0;remoteToken.issue(body+16,now);lastOwned=body[35];
  const bool changed=linkState.observe(secure::route(p),now,rtt);queryRoute=linkState.path;
  if(changed){linkState.resetSamples();clearCommands();status("Route learned; qualifying; commands discarded");nextPoll=now+20;return;}
  for(unsigned i=0;i<count;++i)usbOut(selected,1,frames[i].bytes,frames[i].n);
  if(replyProfile==unified::MANUAL){char text[100];snprintf(text,sizeof(text),"TELERC_LORA_STATUS_V1,%u,%u,%lu,%lu,%u,%lu",unsigned(body[34]),unsigned(body[35]),(unsigned long)mission::u32(body+38),(unsigned long)mission::u32(body+42),unsigned(body[36]),(unsigned long)mission::u32(body+46));usbOut(selected,2,reinterpret_cast<uint8_t*>(text),strlen(text));}
  const uint32_t maxDataAir=(radio.getTimeOnAir(18+telerc::RADIO_MAX+secure::HEAD+secure::NONCE+secure::TAG+secure::MAC)+999)/1000;
  if(queryProfile==unified::HEALTH||!linkState.qualified(now)||(session.profile==unified::MANUAL&&!linkState.manual(now,maxDataAir))){nextPoll=now+(session.fresh(now)||!linkState.qualified(now)?20:1000);return;}
  if(!Serial||!session.fresh(now)){clearCommands();nextPoll=now+100;return;}
  uint8_t down[mission::MAX_PLAIN];size_t used=0;
  if(session.profile==unified::MANUAL){used=mailbox.take(down+18,now);}
  else{
   mission::Frame cmd;bool have=false;mission::Mav first;
   if(commands[0].fresh(now)&&first.parse(commands[0].data,commands[0].n)&&holdFrame(first,selected)){cmd=commands[0];commands[0].clear();have=true;servedHostHeartbeat=false;}
   if(!have&&!servedHostHeartbeat&&heartbeat.fresh(now)){cmd=heartbeat;heartbeat.clear();have=servedHostHeartbeat=true;}
   if(!have&&takeFrame(commands,4,cmd,now,mission::HOST_MS)){have=true;servedHostHeartbeat=false;}
   if(!have&&heartbeat.fresh(now)){cmd=heartbeat;heartbeat.clear();have=servedHostHeartbeat=true;}
   if(have){used=cmd.n;memcpy(down+18,cmd.data,used);}
  }
  if(used){memcpy(down,remoteToken.token,16);down[16]=session.profile;down[17]=used;remoteToken.active=false;
   if(!makePacket(mission::DATA,selected,down,18+used,queryRoute,false,transaction))++dropCount;
   const uint32_t air=(radio.getTimeOnAir(18+used+secure::HEAD+secure::NONCE+secure::TAG+secure::MAC)+999)/1000;
   nextPoll=now+(queryRoute.n+1)*air+2*queryRoute.n+5;
  }else nextPoll=now+20;
  return;
 }
 if(p[3]==mission::SYNC){
  if(len!=17||body[16]<unified::MANUAL||body[16]>unified::HEALTH){++rejectCount;return;}
  if(secure::discovery(p)&&body[16]!=unified::HEALTH){++rejectCount;return;}
  const auto path=secure::route(p);
  if(haveRemoteRoute&&path!=remoteRoute){stopControl(3);gate.invalidate();}
  if(body[16]==unified::HEALTH){stopControl(3);gate.invalidate();}
  haveRemoteRoute=true;remoteProfile=body[16];remoteRoute=path;
  uint8_t response[mission::MAX_PLAIN];memcpy(response,body,16);esp_fill_random(response+16,16);
  // Batch complete MAVLink frames within the existing 100-byte response budget.
  // Genuine FC heartbeat remains present while mission replies make progress.
  remoteToken.issue(response+16,now);
  size_t used=0;unsigned packed=0;
  auto append=[&](mission::Frame&s,uint32_t ttl){
   if(!s.n)return false;
   if(!s.fresh(now,ttl)){s.clear();++dropCount;return false;}
   if(packed>=4||used+s.n>(remoteProfile==unified::MANUAL?48u:mission::MAX_MAV))return false;
   memcpy(response+50+used,s.data,s.n);used+=s.n;++packed;s.clear();return true;
  };
  append(fcHeartbeat,1500);
  for(unsigned i=0;i<4;++i){unsigned slot=(criticalCursor+i)%4;if(append(telemetry[slot],1800)){criticalCursor=(slot+1)%4;break;}}
  const unsigned start=navCursor;
  for(unsigned i=0;i<4;++i){unsigned slot=(start+i)%4;if(append(telemetry[4+slot],1800))navCursor=(slot+1)%4;}
  response[32]=remoteProfile;response[33]=used;
  response[34]=manual.ready&&gate.fresh(now)&&uint32_t(now-gate.hbAt)<unified::FC_MS&&gate.mode==0;response[35]=manual.owned;response[36]=stopReason;response[37]=0;
  for(unsigned i=0;i<4;++i){response[38+i]=stopCount>>(8*i);response[42+i]=bootId>>(8*i);}
  uint32_t age=0;for(unsigned i=0;i<2;++i)if(manual.owned&(1u<<i)){uint32_t a=now-manual.at[i];if(a>age)age=a;}for(unsigned i=0;i<4;++i)response[46+i]=age>>(8*i);
  makePacket(mission::RESPONSE,ROVER_ID,response,50+used,remoteRoute,false,mission::u32(p+16));
 }else if(p[3]==mission::DATA){
  if(len<18||len!=size_t(18+body[17])||body[16]!=remoteProfile||secure::route(p)!=remoteRoute||remoteProfile==unified::HEALTH||!remoteToken.consume(body,now)){++rejectCount;return;}
  if(remoteProfile==unified::MANUAL){acceptManual(body+18,body[17]);return;}
  mission::Mav frame;if(body[17]>mission::MAX_MAV||!frame.parse(body+18,body[17])){++rejectCount;return;}
  if(holdFrame(frame,ROVER_ID))stopControl(3);
  if(manual.owned||stopPending){++rejectCount;return;}
  mission::Gate next=gate;
  if(!next.down(frame,now,SERVO_MASK)||fc.availableForWrite()<int(frame.n)){++rejectCount;return;}
  if(fc.write(frame.bytes,frame.n)==frame.n)gate=next;else{gate.invalidate();stopControl(5);++dropCount;}

 }
}
void makeRc(uint8_t*out,uint16_t value,uint8_t seq){
 memset(out,0,26);out[0]=0xfe;out[1]=18;out[2]=seq;out[3]=255;out[4]=190;out[5]=70;
 for(unsigned i=0;i<8;++i)mission::put16(out+6+2*i,i<2?value:65535);
 out[22]=ROVER_ID;out[23]=1;telerc::CommandMailbox::checksumRc(out);
}
void tryStop(){
 if(ROLE!=2||!stopPending)return;
 uint8_t out[52];makeRc(out,1500,0);makeRc(out+26,0,1);
 if(fc.availableForWrite()>=52&&fc.write(out,52)==52)stopPending=false;
 stopTryAt=millis();
}
void stopControl(uint8_t reason){
 if(ROLE!=2)return;
 if(manual.owned){++stopCount;stopReason=reason;stopPending=true;}
 manual.latch();tryStop();
}
void manualWatchdog(){
 const uint32_t now=millis();
 if(manual.owned){
  if(manual.expired(now))stopControl(1);
  else if(!gate.fresh(now)||uint32_t(now-gate.hbAt)>=unified::FC_MS)stopControl(2);
  else if(gate.mode!=0)stopControl(3);
 }
 if(stopPending&&uint32_t(now-stopTryAt)>=20)tryStop();
}
void acceptManual(const uint8_t*p,size_t n){
 const uint32_t now=millis();
 if(!telerc::validBundle(p,n)){++rejectCount;return;}
 unified::Manual next=manual;bool stop=false,disarm=false;size_t used=0;uint8_t out[telerc::RADIO_MAX];
 // Validate the whole bundle before any UART write. No mission/parameter/servo
 // command is accepted through this manual path, even with a valid AES tag.
 for(size_t i=0;i<n;){size_t k=p[i++];const uint8_t*f=p+i;i+=k;
  if(telerc::textEquals(f,k,"TELERC_DISCONNECT_V1")){stopControl(4);return;}
  if(telerc::textEquals(f,k,"TELERC_DISCOVER_V1"))continue;
  telerc::CommandMailbox shape;mission::Mav m;
  if(!shape.accept(f,k,now)||!m.parse(f,k)){++rejectCount;return;}
  if(unified::Manual::release(m))stop=true;
  if(m.id==76&&mission::real(m.payload)==0){stop=disarm=true;}
 }
 if(stop){stopControl(disarm?7:3);next=manual;}
 for(size_t i=0;i<n;){size_t k=p[i++];const uint8_t*f=p+i;i+=k;mission::Mav m;
  if(!m.parse(f,k))continue;
  if(stop&&(m.id==0||m.id==70||(m.id==76&&mission::real(m.payload)!=0)))continue;
  if(!stop&&!next.accept(m,gate,now)){++rejectCount;return;}
  if(stopPending&&m.id!=0){++rejectCount;return;}
  if(used+k>sizeof(out)){++rejectCount;return;}memcpy(out+used,f,k);used+=k;
 }
 manual=next;
 if(manual.owned)gate.invalidate();
 if(used&&(fc.availableForWrite()<int(used)||fc.write(out,used)!=used)){++dropCount;stopControl(5);}
}
void pumpRadio(){
 if(!running)return;uint32_t now=millis();
 if(transmitting){
  if(irq){irq=false;int s=radio.finishTransmit();transmitting=false;if(s!=RADIOLIB_ERR_NONE){fault();return;}receiveMode();}
  else if(uint32_t(now-txAt)>txLimit){if(radio.getIrqFlags()&RADIOLIB_SX126X_IRQ_TX_DONE)irq=true;else fault();}return;
 }
 if(digitalRead(33)==HIGH)irq=true;
 if(irq){
  irq=false;uint8_t packet[secure::MAX];size_t n=radio.getPacketLength();
  if(n>sizeof(packet)||n<secure::HEAD+secure::NONCE+secure::TAG+secure::MAC){radio.standby();receiveMode();++rejectCount;}
  else{int s=radio.readData(packet,n);if(!receiveMode())return;if(s==RADIOLIB_ERR_NONE)onPacket(packet,n);else ++rejectCount;}
 }
 if(pending.n&&int32_t(now-pending.due)>=0){
  if(uint32_t(now-pending.at)>500){pending.n=0;++dropCount;return;}
  irq=false;txLimit=(radio.getTimeOnAir(pending.n)+999)/1000+100;txAt=now;
  uint8_t kind=pending.kind;
  int s=radio.startTransmit(pending.bytes,pending.n);pending.n=0;
  if(s!=RADIOLIB_ERR_NONE){fault();return;}transmitting=true;++txCount;
  if(ROLE==1&&kind==mission::SYNC){waiting=true;baseQuery.at=now;}
 }
}
bool claimHost(uint8_t profile,uint8_t id,uint32_t now){
 const bool changed=session.profile!=profile||session.rover!=id;
 if(changed&&(transmitting||pending.n))return false;
 if(!session.claim(profile,id,now))return false;
 if(changed){clearCommands();waiting=false;baseQuery.active=false;if(selected!=id)linkState.clear();selected=id;nextPoll=now;}
 hostAt=now;return true;
}
void legacyUsb(const uint8_t*p,size_t n){
 const uint32_t now=millis();
 if(telerc::textEquals(p,n,"TELERC_LORA_GET_V1")){
  replyProfile=unified::MANUAL;uint8_t fingerprint[secure::MAC];const uint8_t label[]={85,78,73,70,73,69,68};secure::mac(ROUTE_KEY,label,sizeof(label),fingerprint);char caps[100];snprintf(caps,sizeof(caps),"TELERC_LORA_INFO_V2,BASE,1262,%u,%lu,%u,%04x,0,0,0,0,ARDUROVER",running?1u:0u,(unsigned long)(FREQUENCY_MHZ*1000),unsigned(POWER_DBM),unsigned(mission::u16(fingerprint)));usbOut(1,3,reinterpret_cast<uint8_t*>(caps),strlen(caps));return;
 }
 if(n>=19&&!memcmp(p,"TELERC_LORA_SET_V1,",19)){const char*text="TELERC_LORA_RESULT_V1,SKETCH_PAIRING_LOCKED";usbOut(1,2,reinterpret_cast<const uint8_t*>(text),strlen(text));return;}
 telerc::CommandMailbox next=mailbox;
 if(!running||!next.accept(p,n,now)||!claimHost(unified::MANUAL,1,now)){++rejectCount;return;}
 mailbox=next;
}
void missionUsb(){
 auto p=usbParser.buf;uint8_t id=p[2];size_t n=mission::u16(p+4);mission::Mav frame;const uint32_t now=millis();
 if(!roverKey(id))return;
 if(p[3]==3&&n==4&&!memcmp(p+6,"INFO",4)){
  replyProfile=unified::MISSION;char caps[100];snprintf(caps,sizeof(caps),"TM2;fw=0.2.0;relays=%u;mask=%u;unified=0.4.0",unsigned(RELAY_COUNT),unsigned(SERVO_MASK));usbOut(id,3,reinterpret_cast<uint8_t*>(caps),strlen(caps));return;
 }
 if(p[3]!=1||!frame.parse(p+6,n)||frame.sys!=255||frame.comp!=190||!running||!claimHost(unified::MISSION,id,now)){++rejectCount;return;}
 if(holdFrame(frame,id)){clearCommands();if(!transmitting&&pending.kind==mission::DATA)pending.n=0;commands[0].set(p+6,n,now);}
 else if(frame.id==0)heartbeat.set(p+6,n,now);
 else if(!pushFrame(commands,4,p+6,n,now))status("Command queue full");
}
void pumpUsb(){
 // Both CRC-framed decoders identify INFO only; active traffic follows its
 // selected framing, so an ambiguous prefix never becomes a second command.
 for(unsigned i=0;i<512&&Serial.available();++i){const uint8_t byte=Serial.read();const uint32_t now=millis();
  bool legacy=legacyParser.feed(byte,now),mission=usbParser.feed(byte,now);
  if(legacy){const auto*p=legacyParser.data+4;size_t n=legacyParser.length();
   if(telerc::textEquals(p,n,"TELERC_LORA_GET_V1")||replyProfile==unified::MANUAL)legacyUsb(p,n);
  }
  if(mission&&(usbParser.buf[3]==3||replyProfile==unified::MISSION))missionUsb();
 }
}
void pumpFc(){
 mission::Mav frame;uint32_t now=millis();gate.tick(now);
 for(unsigned i=0;i<512&&fc.available();++i)if(fcParser.feed(fc.read(),now,frame)){
  const bool reboot=frame.id==33&&frame.sys==ROVER_ID&&frame.comp==1&&gate.haveBoot&&int32_t(mission::u32(frame.payload)-gate.bootMs)<0;
  const bool wasArmed=gate.armed;
  if(!gate.fromFc(frame,now))continue;
  if(reboot){stopControl(2);gate.haveHb=false;fcHeartbeat.clear();}
  if(frame.id==0&&wasArmed&&!gate.armed)stopControl(7);
  if(frame.id==0&&gate.armed&&gate.uploading)gate.invalidate();
  if(frame.id==0)fcHeartbeat.set(frame.bytes,frame.n,now);
  else if(frame.id==40||frame.id==51||frame.id==44||frame.id==39||frame.id==73||frame.id==47||frame.id==77||frame.id==22)pushFrame(telemetry,4,frame.bytes,frame.n,now);
  else if(frame.id==1||frame.id==24||frame.id==33||frame.id==42||frame.id==46||frame.id==253){
   bool replaced=false;for(unsigned j=4;j<8;++j){auto&slot=telemetry[j];if(slot.n){mission::Mav old;if(old.parse(slot.data,slot.n)&&old.id==frame.id){slot.set(frame.bytes,frame.n,now);replaced=true;break;}}}
   if(!replaced)pushFrame(telemetry+4,4,frame.bytes,frame.n,now);
  }
 }
}
void poll(){
 uint32_t now=millis();if(transmitting||pending.n)return;
 const uint32_t timeout=discovering?mission::TOKEN_MS:(queryProfile==unified::MISSION?mission::TOKEN_MS:700);
 if(waiting){if(uint32_t(now-baseQuery.at)<=timeout)return;waiting=false;baseQuery.active=false;++dropCount;
  if(!linkState.qualified(now))linkState.resetSamples();
  if(++misses>=3||discovering){misses=0;linkState.clear();clearCommands();status("Route lost; commands discarded; rediscovering");}
 }
 if(!session.fresh(now))clearCommands();
 if(int32_t(now-nextPoll)<0)return;
 if(!selected)selected=1;if(!roverKey(selected))return;
 const uint32_t maxDataAir=(radio.getTimeOnAir(18+telerc::RADIO_MAX+secure::HEAD+secure::NONCE+secure::TAG+secure::MAC)+999)/1000;
 if(session.fresh(now)&&session.profile==unified::MANUAL&&linkState.qualified(now)&&!linkState.manual(now,maxDataAir)){
  clearCommands();linkState.clear();status("Route too slow for manual; searching; no control commands");
 }
 if(!linkState.fresh(now)){linkState.clear();if(haveDiscovery&&uint32_t(now-discoveryAt)<mesh::DISCOVERY_MS)return;}
 discovering=!linkState.known;queryRoute=discovering?mesh::Route{}:linkState.path;
 queryProfile=(!discovering&&linkState.qualified(now)&&session.fresh(now)&&
  (session.profile!=unified::MANUAL||linkState.manual(now,maxDataAir)))?session.profile:unified::HEALTH;
 uint8_t query[17];esp_fill_random(query,16);query[16]=queryProfile;esp_fill_random(&transaction,sizeof(transaction));baseQuery.issue(query,now);
 if(makePacket(mission::SYNC,selected,query,17,queryRoute,discovering,transaction)){
  if(discovering){haveDiscovery=true;discoveryAt=now;status("Discovering nodes; no control commands");}
 }else baseQuery.active=false;
}
void display(){
 uint32_t now=millis();static bool button=false;bool pressed=digitalRead(0)==LOW;
 if(pressed&&!button){wakeAt=now;oled.setAwake(true);}button=pressed;
 if(uint32_t(now-wakeAt)>=30000&&!oled.asleep)oled.setAwake(false);
 if(uint32_t(now-displayAt)>=1000){
  displayAt=now;char row0[24],row1[24],row2[24],row3[24],row4[24],row5[24];
  snprintf(row0,sizeof(row0),"SCALE 0.4.0 RC1");snprintf(row1,sizeof(row1),"%s ID %u",ROLE==1?"BASE":ROLE==2?"ROVER":"NODE",ROLE==1?selected:ROLE==2?ROVER_ID:NODE_ID);
  snprintf(row2,sizeof(row2),"RF %s %.1f MHZ",running?"OK":"OFF",double(FREQUENCY_MHZ));
  snprintf(row3,sizeof(row3),"RX %lu TX %lu",(unsigned long)(rxCount%100000),(unsigned long)(txCount%100000));
  snprintf(row4,sizeof(row4),"REJ %lu DROP %lu",(unsigned long)(rejectCount%100000),(unsigned long)(dropCount%100000));
  snprintf(row5,sizeof(row5),"%s",ROLE==3?(nodeReplyAt&&uint32_t(now-nodeReplyAt)<7000?"NODE READY":"NODE STANDBY"):ROLE==2?(gate.fresh(now)?(gate.armed?"FC ARMED":"FC DISARMED"):"WAIT FC"):(linkState.qualified(now)?"ROUTE QUALIFIED":"DISCOVER / QUALIFY"));
  const char*rows[]={row0,row1,row2,row3,row4,row5,"BOOT WAKES DISPLAY","NO AUTO ARM"};oled.rows(rows);
 }
 oled.step();digitalWrite(37,running?(uint32_t(now%1000)<(rxCount?80:400)):((now/150)%2));
}
bool startRadio(){
 radioRetryAt=millis();stopped=true;
 if(radio.begin(FREQUENCY_MHZ,500.0,7,5,0x12,POWER_DBM,8,1.6)!=RADIOLIB_ERR_NONE)return false;
 if(radio.setRxBoostedGainMode(true,true)!=RADIOLIB_ERR_NONE)return false;
 radio.setDio1Action(radioInterrupt);running=true;stopped=false;rxRearmAt=millis();return receiveMode();
}
void setup(){
 // LoRa is a separate radio; it does not enable ESP32 Wi-Fi entropy. Keep the
 // internal ADC entropy source enabled (no ADC/battery measurements here).
 bootloader_random_enable();
 do{esp_fill_random(&bootId,sizeof(bootId));}while(!bootId);
 Serial.begin(115200);Serial.setTxTimeoutMs(1);pinMode(0,INPUT_PULLUP);pinMode(37,OUTPUT);oled.begin();wakeAt=millis();
 if(!PROVISIONED||!keySet(ROUTE_KEY)){stopped=true;return;}
 if(ROLE!=3)for(const auto&v:ROVERS)if(!v.id||v.id>20||!keySet(v.key)){stopped=true;return;}
 if(ROLE==2&&!roverKey(ROVER_ID)){stopped=true;return;}
 if(ROLE==2){fc.setRxBufferSize(2048);fc.setTxBufferSize(512);fc.begin(115200,SERIAL_8N1,44,43);}
 SPI.begin(5,3,6,7);
 authorizedRadio=true;startRadio();
}
void loop(){
 if(authorizedRadio&&!running&&uint32_t(millis()-radioRetryAt)>=2000)startRadio();
 if(running&&!transmitting&&!pending.n&&!waiting&&uint32_t(millis()-rxRearmAt)>=5000){rxRearmAt=millis();receiveMode();}
 if(ROLE==1&&!Serial){clearCommands();waiting=false;baseQuery.active=false;if(!transmitting)pending.n=0;}
 if(ROLE==1)pumpUsb();if(ROLE==2){pumpFc();manualWatchdog();}pumpRadio();if(ROLE==1&&running)poll();
 if(ROLE==1&&millis()-diagAt>3000){diagAt=millis();status(running?"UNIFIED; RF initialized; real FC telemetry required":"RF OFF; check provisioning/radio");}
 display();delay(1);
}
