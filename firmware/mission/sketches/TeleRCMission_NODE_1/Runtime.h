#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <bootloader_random.h>
#include "Config.h"
#include "Crypto.h"
#include "TinyOled.h"

#if defined(ARDUINO_ARCH_ESP32)
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "TeleRC Mission requires the ESP32-S3 LilyGO SX1262 board profile"
#endif
#if !ARDUINO_USB_CDC_ON_BOOT || !ARDUINO_USB_MODE
#error "Enable USB CDC On Boot and Hardware CDC/JTAG USB mode"
#endif
#endif

static_assert(ROLE>=1&&ROLE<=3,"Invalid role");
static_assert(RELAY_COUNT>=0&&RELAY_COUNT<=2,"At most two serial relays");
static_assert(ROLE!=3||(NODE_INDEX>=1&&NODE_INDEX<=RELAY_COUNT),"Invalid relay index");
static_assert(ROVER_ID>=1&&ROVER_ID<=20,"Rover ID must be 1..20");
static_assert(POWER_DBM>=2&&POWER_DBM<=17,"Power 2..17 dBm only");
SX1262 radio=new Module(7,33,8,34);
HardwareSerial fc(1);
telerc::TinyOled oled;
mission::Gate gate(ROVER_ID);
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
struct Seen {uint8_t nonce[12]={};uint32_t at=0;bool valid=false;} seen[16];unsigned seenIndex=0;
void IRAM_ATTR radioInterrupt(){irq=true;}
const uint8_t* roverKey(uint8_t id){for(const auto&v:ROVERS)if(v.id==id)return v.key;return nullptr;}
bool keySet(const uint8_t*p){uint8_t any=0;for(unsigned i=0;i<32;++i)any|=p[i];return any;}
bool holdFrame(const mission::Mav&m,uint8_t id){
 const auto*p=m.payload;
 return m.id==76&&m.sys==255&&m.comp==190&&p[30]==id&&p[31]==1&&mission::u16(p+28)==176&&mission::real(p)==1&&mission::real(p+4)==4;
}
void clearCommands(){for(auto&s:commands)s.clear();heartbeat.clear();remoteToken.active=false;}
void usbOut(uint8_t id,uint8_t type,const uint8_t*p,size_t n){
 if(!n||n>mission::MAX_MAV)return;uint8_t out[mission::MAX_MAV+8];out[0]=0xa5;out[1]=0x5a;out[2]=id;out[3]=type;
 mission::put16(out+4,n);memcpy(out+6,p,n);mission::put16(out+6+n,mission::crc(out+2,n+4));
 // CDC disconnected/full must not block the RF receive loop.
 if(Serial&&Serial.availableForWrite()>=int(n+8))Serial.write(out,n+8);else ++dropCount;
}
void status(const char*msg){if(ROLE==1)usbOut(selected,2,reinterpret_cast<const uint8_t*>(msg),strlen(msg));}
void fault(){running=false;stopped=true;waiting=false;pending.n=0;clearCommands();radio.standby();status("RF fault; reset required; no auto-resume");}
bool receiveMode(){irq=false;int s=radio.startReceive();if(s!=RADIOLIB_ERR_NONE){fault();return false;}return true;}
bool queuePacket(const uint8_t*p,size_t n,uint8_t kind,uint32_t delayMs=5){
 if(pending.n||transmitting||n>sizeof(pending.bytes)){++dropCount;return false;}
 memcpy(pending.bytes,p,n);pending.n=n;pending.kind=kind;pending.at=millis();pending.due=millis()+delayMs;return true;
}
bool makePacket(uint8_t kind,uint8_t id,const uint8_t*body,size_t n){
 const auto*key=roverKey(id);if(!key)return false;uint8_t packet[secure::MAX];
 size_t size=secure::seal(packet,kind,FLEET_ID,id,RELAY_COUNT,kind==mission::RESPONSE?1:0,body,n,key,ROUTE_KEY);
 return size&&queuePacket(packet,size,kind);
}
bool duplicate(const uint8_t*p,uint32_t now){
 for(const auto&s:seen)if(s.valid&&uint32_t(now-s.at)<10000&&mission::equal(s.nonce,p+secure::HEAD,12))return true;
 auto&s=seen[seenIndex++%16];memcpy(s.nonce,p+secure::HEAD,12);s.at=now;s.valid=true;return false;
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
 if(!secure::hopValid(p,n,ROUTE_KEY,FLEET_ID,RELAY_COUNT)){++rejectCount;return;}
 if(ROLE==3){
  uint8_t expected=p[8]==0?NODE_INDEX-1:RELAY_COUNT-NODE_INDEX;
  if(p[9]!=expected||duplicate(p,now)){++rejectCount;return;}
  if(!secure::advance(p,n,ROUTE_KEY)||!queuePacket(p,n,p[3],8)){++dropCount;}return;
 }
 uint8_t id=p[6];
 if(p[9]!=RELAY_COUNT||(ROLE==1?(id!=selected||p[8]!=1||p[3]!=mission::RESPONSE):(id!=ROVER_ID||p[8]!=0||p[3]==mission::RESPONSE))){++rejectCount;return;}
 if(duplicate(p,now)){++rejectCount;return;}
 const uint8_t*key=roverKey(id);uint8_t body[mission::MAX_PLAIN];
 if(!key||!secure::open(p,n,body,key)){++rejectCount;return;}
 size_t len=mission::u16(p+10);++rxCount;
 if(ROLE==1){
  if(!waiting||len<33||!baseQuery.consume(body,now)){++rejectCount;return;}
  waiting=false;remoteToken.issue(body+16,now);
  size_t mavLen=body[32];if(len!=33+mavLen||mavLen>mission::MAX_MAV){++rejectCount;return;}
  size_t cursor=0;mission::Mav frames[4];unsigned count=0;
  while(cursor<mavLen&&count<4){
   auto*q=body+33+cursor;
   if(mavLen-cursor<2||(q[0]!=0xfe&&q[0]!=0xfd)){++rejectCount;return;}
   size_t frameLen=q[1]+(q[0]==0xfd?12:8);
   if(frameLen>mavLen-cursor||!frames[count].parse(q,frameLen)||frames[count].sys!=selected||frames[count].comp!=1){++rejectCount;return;}
   cursor+=frameLen;++count;
  }
  if(cursor!=mavLen){++rejectCount;return;}
  for(unsigned i=0;i<count;++i)usbOut(selected,1,frames[i].bytes,frames[i].n);
  if(!Serial||uint32_t(now-hostAt)>mission::HOST_MS){clearCommands();return;}
  mission::Frame cmd;
  bool haveCommand=false;
  mission::Mav first;
  if(commands[0].fresh(now)&&first.parse(commands[0].data,commands[0].n)&&holdFrame(first,selected)){
   cmd=commands[0];commands[0].clear();haveCommand=true;servedHostHeartbeat=false;
  }
  // A busy mission transfer must not starve the actual host heartbeat.
  if(!haveCommand&&!servedHostHeartbeat&&heartbeat.fresh(now)){
   cmd=heartbeat;heartbeat.clear();haveCommand=servedHostHeartbeat=true;
  }
  if(!haveCommand&&takeFrame(commands,4,cmd,now,mission::HOST_MS)){haveCommand=true;servedHostHeartbeat=false;}
  if(!haveCommand&&heartbeat.fresh(now)){cmd=heartbeat;heartbeat.clear();haveCommand=servedHostHeartbeat=true;}
  if(haveCommand){
   uint8_t down[mission::MAX_PLAIN];memcpy(down,remoteToken.token,16);down[16]=cmd.n;memcpy(down+17,cmd.data,cmd.n);
   remoteToken.active=false;if(!makePacket(mission::DATA,selected,down,17+cmd.n))++dropCount;
  }
  nextPoll=now+220+RELAY_COUNT*180;return;
 }
 if(p[3]==mission::SYNC){
  if(len!=16){++rejectCount;return;}
  uint8_t response[mission::MAX_PLAIN];memcpy(response,body,16);esp_fill_random(response+16,16);
  // Batch complete MAVLink frames within the existing 100-byte response budget.
  // Genuine FC heartbeat remains present while mission replies make progress.
  remoteToken.issue(response+16,now);
  size_t used=0;unsigned packed=0;
  auto append=[&](mission::Frame&s,uint32_t ttl){
   if(!s.n)return false;
   if(!s.fresh(now,ttl)){s.clear();++dropCount;return false;}
   if(packed>=4||used+s.n>mission::MAX_MAV)return false;
   memcpy(response+33+used,s.data,s.n);used+=s.n;++packed;s.clear();return true;
  };
  append(fcHeartbeat,1500);
  for(unsigned i=0;i<4;++i){unsigned slot=(criticalCursor+i)%4;if(append(telemetry[slot],1800)){criticalCursor=(slot+1)%4;break;}}
  const unsigned start=navCursor;
  for(unsigned i=0;i<4;++i){unsigned slot=(start+i)%4;if(append(telemetry[4+slot],1800))navCursor=(slot+1)%4;}
  response[32]=used;
  makePacket(mission::RESPONSE,ROVER_ID,response,33+used);
 }else if(p[3]==mission::DATA){
  if(len<17||len!=size_t(17+body[16])||body[16]>mission::MAX_MAV||!remoteToken.consume(body,now)){++rejectCount;return;}
  mission::Mav frame;if(!frame.parse(body+17,body[16])){++rejectCount;return;}
  // Commit state only after one complete nonblocking UART write succeeds.
  mission::Gate next=gate;
  if(!next.down(frame,now,SERVO_MASK)||fc.availableForWrite()<int(frame.n)){++rejectCount;return;}
  if(fc.write(frame.bytes,frame.n)==frame.n)gate=next;else{gate.invalidate();++dropCount;}
 }
}
void pumpRadio(){
 if(!running)return;uint32_t now=millis();
 if(transmitting){
  if(irq){irq=false;int s=radio.finishTransmit();transmitting=false;if(s!=RADIOLIB_ERR_NONE){fault();return;}receiveMode();}
  else if(uint32_t(now-txAt)>txLimit)fault();return;
 }
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
void pumpUsb(){
 uint32_t now=millis();
 for(unsigned i=0;i<512&&Serial.available();++i)if(usbParser.feed(Serial.read(),now)){
  auto p=usbParser.buf;uint8_t id=p[2];size_t n=mission::u16(p+4);mission::Mav frame;
  if(p[3]==3&&roverKey(id)&&n==4&&!memcmp(p+6,"INFO",4)){
   char caps[96];snprintf(caps,sizeof(caps),"TM2;fw=0.2.0;relays=%u;mask=%u",unsigned(RELAY_COUNT),unsigned(SERVO_MASK));
   usbOut(id,3,reinterpret_cast<const uint8_t*>(caps),strlen(caps));continue;
  }
  if(p[3]!=1||!roverKey(id)||!frame.parse(p+6,n)||frame.sys!=255||frame.comp!=190){++rejectCount;continue;}
  // Target changes require 5 seconds of host silence and drop all old work.
  if(selected!=id){
   if(selected&&uint32_t(now-hostAt)<5000){++rejectCount;continue;}
   if(transmitting||pending.n){++rejectCount;continue;}
   clearCommands();waiting=false;baseQuery.active=false;selected=id;nextPoll=now;
  }
  hostAt=now;
  if(holdFrame(frame,id)){
   // Cancel work still local to BASE. Frames already on air cannot be recalled.
   clearCommands();
   if(!transmitting&&pending.kind==mission::DATA)pending.n=0;
   commands[0].set(p+6,n,now);
  }
  else if(frame.id==0)heartbeat.set(p+6,n,now);
  else if(!pushFrame(commands,4,p+6,n,now))status("Command queue full; retry at mission protocol level");
 }
}
void pumpFc(){
 mission::Mav frame;uint32_t now=millis();gate.tick(now);
 for(unsigned i=0;i<512&&fc.available();++i)if(fcParser.feed(fc.read(),now,frame)&&gate.fromFc(frame,now)){
  if(frame.id==0)fcHeartbeat.set(frame.bytes,frame.n,now);
  else if(frame.id==40||frame.id==51||frame.id==44||frame.id==39||frame.id==73||frame.id==47||frame.id==77||frame.id==22)
   pushFrame(telemetry,4,frame.bytes,frame.n,now);
  // Other navigation/status streams coalesce: never queue a high-rate stream.
  else if(frame.id==24||frame.id==33||frame.id==42||frame.id==46||frame.id==253){
   bool replaced=false;
   for(unsigned j=4;j<8;++j){auto&s=telemetry[j];if(s.n){mission::Mav old;if(old.parse(s.data,s.n)&&old.id==frame.id){s.set(frame.bytes,frame.n,now);replaced=true;break;}}}
   if(!replaced)pushFrame(telemetry+4,4,frame.bytes,frame.n,now);
  }
 }
}
void poll(){
 uint32_t now=millis();if(transmitting||pending.n)return;
 if(!Serial){clearCommands();waiting=false;baseQuery.active=false;return;}
 if(waiting){if(uint32_t(now-baseQuery.at)<=mission::TOKEN_MS)return;waiting=false;baseQuery.active=false;++dropCount;}
 if(!selected||uint32_t(now-hostAt)>mission::HOST_MS){clearCommands();return;}
 if(int32_t(now-nextPoll)<0)return;
 uint8_t query[16];esp_fill_random(query,16);baseQuery.issue(query,now);
 if(!makePacket(mission::SYNC,selected,query,16))baseQuery.active=false;
}
void display(){
 uint32_t now=millis();static bool button=false;bool pressed=digitalRead(0)==LOW;
 if(pressed&&!button){wakeAt=now;oled.setAwake(true);}button=pressed;
 if(uint32_t(now-wakeAt)>=30000&&!oled.asleep)oled.setAwake(false);
 if(uint32_t(now-displayAt)>=1000){
  displayAt=now;char row0[24],row1[24],row2[24],row3[24],row4[24],row5[24];
  snprintf(row0,sizeof(row0),"MISSION RC 0.2.0");snprintf(row1,sizeof(row1),"%s ID %u",ROLE==1?"BASE":ROLE==2?"ROVER":"NODE",ROLE==1?selected:ROLE==2?ROVER_ID:NODE_INDEX);
  snprintf(row2,sizeof(row2),"RF %s %.1f MHZ",running?"OK":"OFF",double(FREQUENCY_MHZ));
  snprintf(row3,sizeof(row3),"RX %lu TX %lu",(unsigned long)(rxCount%100000),(unsigned long)(txCount%100000));
  snprintf(row4,sizeof(row4),"REJ %lu DROP %lu",(unsigned long)(rejectCount%100000),(unsigned long)(dropCount%100000));
  snprintf(row5,sizeof(row5),"%s",ROLE==2?(gate.fresh(now)?(gate.armed?"FC ARMED":"FC DISARMED"):"WAIT FC"):"MISSION ONLY");
  const char*rows[]={row0,row1,row2,row3,row4,row5,"BOOT WAKES DISPLAY","NO AUTO ARM"};oled.rows(rows);
 }
 oled.step();digitalWrite(37,running?(uint32_t(now%1000)<(rxCount?80:400)):((now/150)%2));
}
void setup(){
 // LoRa is a separate radio; it does not enable ESP32 Wi-Fi entropy. Keep the
 // internal ADC entropy source enabled (no ADC/battery measurements here).
 bootloader_random_enable();
 Serial.begin(115200);Serial.setTxTimeoutMs(1);pinMode(0,INPUT_PULLUP);pinMode(37,OUTPUT);oled.begin();wakeAt=millis();
 if(!PROVISIONED||!keySet(ROUTE_KEY)){stopped=true;return;}
 if(ROLE!=3)for(const auto&v:ROVERS)if(!v.id||v.id>20||!keySet(v.key)){stopped=true;return;}
 if(ROLE==2&&!roverKey(ROVER_ID)){stopped=true;return;}
 if(ROLE==2){fc.setRxBufferSize(2048);fc.setTxBufferSize(512);fc.begin(115200,SERIAL_8N1,44,43);}
 SPI.begin(5,3,6,7);
 if(radio.begin(FREQUENCY_MHZ,250.0,7,5,0x12,POWER_DBM,8,1.6)!=RADIOLIB_ERR_NONE){stopped=true;return;}
 if(radio.setRxBoostedGainMode(true,true)!=RADIOLIB_ERR_NONE){stopped=true;return;}
 radio.setDio1Action(radioInterrupt);running=true;receiveMode();
}
void loop(){
 if(ROLE==1&&!Serial){clearCommands();waiting=false;baseQuery.active=false;if(!transmitting)pending.n=0;}
 if(ROLE==1)pumpUsb();if(ROLE==2)pumpFc();pumpRadio();if(ROLE==1&&running)poll();
 if(ROLE==1&&millis()-diagAt>3000){diagAt=millis();status(running?"MISSION_ONLY; RF initialized; FC telemetry proves connectivity":"RF OFF; check provisioning/radio; reset required");}
 display();delay(1);
}
