#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <bootloader_random.h>
#include "NetworkConfig.h"
#include "Crypto.h"
#include "Identity.h"
#include "TinyOled.h"
#if defined(ARDUINO_ARCH_ESP32)
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Requires ESP32-S3 LilyGO T3-S3 SX1262"
#endif
#if !ARDUINO_USB_CDC_ON_BOOT || !ARDUINO_USB_MODE
#error "Enable USB CDC on boot and hardware CDC/JTAG"
#endif
#endif
#ifndef ROVER_ID
#define ROVER_ID 1
#endif
#ifndef NODE_ID
#define NODE_ID 1
#endif
static_assert(ROLE>=1&&ROLE<=3,"Invalid role");
static_assert(ROVER_ID>=1&&ROVER_ID<=20,"ROVER_ID must be 1..20");
static_assert(NODE_ID>=1&&NODE_ID<=200,"NODE_ID must be 1..200");
static_assert(POWER_DBM>=2&&POWER_DBM<=17,"Power must be 2..17 dBm");
static_assert(FLEET_ID>=1&&FLEET_ID<=65535,"Invalid fleet ID");
SX1262 radio=new Module(7,33,8,34);
HardwareSerial fc(1);telerc::TinyOled oled;
mission::Gate gate(ROVER_ID);
mission::MavStream fcParser;mission::HostStream usbParser;
mission::Frame commands[4],heartbeat,telemetry[8],fcHeartbeat;
mission::Challenge remoteToken,baseQuery,nodeQuery;
fleet::Identity roverIdentity[secure::MAX_ROVERS],nodeIdentity[secure::MAX_NODE_ID];
uint8_t endpointKey[32]={};
uint8_t selected=0,owner=0,path[secure::MAX_HOPS]={},pathCount=0;
uint8_t watch[secure::MAX_ROVERS]={};unsigned watchCount=secure::MAX_ROVERS,watchCursor=0;
uint32_t hostAt=0,nextPoll=0,txAt=0,txLimit=0,displayAt=0,wakeAt=0,diagAt=0;
uint32_t recoveryAt=0,rxAt=0,nextHello=0,nodeReadyAt=0,nodeForwardAt=0;
bool running=false,transmitting=false,scanning=false,waiting=false,stopped=false,nodeReady=false;
bool servedHostHeartbeat=false;
unsigned criticalCursor=0,navCursor=0;
volatile bool irq=false;
uint32_t rxCount=0,txCount=0,rejectCount=0,dropCount=0;
struct Pending {uint8_t bytes[secure::MAX]={};size_t n=0;uint32_t due=0,at=0;uint8_t kind=0;} pending;
struct Seen {uint8_t nonce[12]={};uint32_t at=0;bool valid=false;} seen[48];unsigned seenIndex=0;
void IRAM_ATTR radioInterrupt(){irq=true;}
bool keySet(const uint8_t*p){uint8_t any=0;for(unsigned i=0;i<32;++i)any|=p[i];return any;}
bool keyFor(uint8_t id,uint8_t*out){
#if ROLE != 3
 return secure::derive(ENDPOINT_ROOT,FLEET_ID,id,out);
#else
 (void)id;(void)out;return false;
#endif
}
bool holdFrame(const mission::Mav&m,uint8_t id){
 const auto*p=m.payload;
 return m.id==76&&m.sys==255&&m.comp==190&&p[30]==id&&p[31]==1&&mission::u16(p+28)==176&&mission::real(p)==1&&mission::real(p+4)==4;
}
void clearCommands(){for(auto&s:commands)s.clear();heartbeat.clear();remoteToken.active=false;servedHostHeartbeat=false;}
void usbOut(uint8_t id,uint8_t type,const uint8_t*p,size_t n){
 if(!n||n>mission::MAX_MAV)return;uint8_t out[mission::MAX_MAV+8];out[0]=0xa5;out[1]=0x5a;out[2]=id;out[3]=type;
 mission::put16(out+4,n);memcpy(out+6,p,n);mission::put16(out+6+n,mission::crc(out+2,n+4));
 if(Serial&&Serial.availableForWrite()>=int(n+8))Serial.write(out,n+8);else ++dropCount;
}
void status(const char*msg){if(ROLE==1)usbOut(selected?selected:1,2,reinterpret_cast<const uint8_t*>(msg),strlen(msg));}
void fault(){
 running=false;transmitting=scanning=waiting=false;pending.n=0;clearCommands();baseQuery.active=false;nodeQuery.active=false;
 if(ROLE==2)gate.invalidate();nodeReady=false;radio.standby();recoveryAt=millis()+2000;status("RF recovery; queued commands discarded; no mission restart");
}
bool receiveMode(){irq=false;int s=radio.startReceive();if(s!=RADIOLIB_ERR_NONE){fault();return false;}rxAt=millis();return true;}
bool queuePacket(const uint8_t*p,size_t n,uint8_t kind,uint32_t delayMs=5){
 // Discovery/health traffic never displaces an already queued mission packet.
 if(pending.n&&pending.kind>=secure::HELLO&&kind<secure::HELLO&&!transmitting&&!scanning)pending.n=0;
 if(pending.n||transmitting||scanning||n>sizeof(pending.bytes)){++dropCount;return false;}
 memcpy(pending.bytes,p,n);pending.n=n;pending.kind=kind;pending.at=millis();pending.due=millis()+delayMs;return true;
}
bool makePacket(uint8_t kind,uint8_t id,const uint8_t*body,size_t n,const uint8_t*route=nullptr,uint8_t count=0){
 uint8_t key[32],packet[secure::MAX];if(!keyFor(id,key))return false;
 size_t size=secure::seal(packet,kind,FLEET_ID,id,route,count,body,n,key,ROUTE_KEY);memset(key,0,32);
 return size&&queuePacket(packet,size,kind,5+(esp_random()%25));
}
bool duplicate(const uint8_t*p,uint32_t now){
 for(const auto&s:seen)if(s.valid&&uint32_t(now-s.at)<10000&&mission::equal(s.nonce,p+secure::HEAD,12))return true;
 auto&s=seen[seenIndex++%48];memcpy(s.nonce,p+secure::HEAD,12);s.at=now;s.valid=true;return false;
}
bool takeFrame(mission::Frame*slots,size_t count,mission::Frame&out,uint32_t now,uint32_t ttl){
 for(size_t i=0;i<count;++i){auto&s=slots[i];if(!s.n)continue;if(!s.fresh(now,ttl)){s.clear();++dropCount;continue;}out=s;s.clear();return true;}return false;
}
bool pushFrame(mission::Frame*slots,size_t count,const uint8_t*p,size_t n,uint32_t now){
 for(size_t i=0;i<count;++i)if(!slots[i].n)return slots[i].set(p,n,now);++dropCount;return false;
}
void helloPacket(uint8_t*p,size_t n,uint32_t now){
 uint8_t body[mission::MAX_PLAIN];size_t len=mission::u16(p+10);
 if(!secure::open(p,n,body,ROUTE_KEY)){++rejectCount;return;}
 if(ROLE==1&&p[3]==secure::HELLO){
  if(len!=25||body[24]!=p[14]||!body[24]||body[24]>secure::MAX_NODE_ID||duplicate(p,now)){++rejectCount;return;}
  bool ok=nodeIdentity[body[24]-1].observe(fleet::readId(body+16),now);
  uint8_t reverse[secure::MAX_HOPS],out[secure::MAX];for(unsigned i=0;i<p[7];++i)reverse[i]=p[14+p[7]-1-i];
  body[25]=ok?1:0;size_t size=secure::seal(out,secure::HELLO_ACK,FLEET_ID,0,reverse,p[7],body,26,ROUTE_KEY,ROUTE_KEY);
  if(size)queuePacket(out,size,secure::HELLO_ACK,10+(esp_random()%30));
  char msg[80];snprintf(msg,sizeof(msg),"NODE %u %s hops=%u",body[24],ok?"READY":"ID_CONFLICT",p[7]);status(msg);return;
 }
 if(ROLE==3&&p[3]==secure::HELLO_ACK&&p[7]&&p[9]==p[7]-1&&secure::forNode(p,NODE_ID)){
  if(len!=26||body[24]!=NODE_ID||fleet::readId(body+16)!=ESP.getEfuseMac()||!nodeQuery.consume(body,now)){++rejectCount;return;}
  nodeReady=body[25]==1;nodeReadyAt=now;++rxCount;return;
 }
 ++rejectCount;
}
void onPacket(uint8_t*p,size_t n){
 uint32_t now=millis();if(!secure::hopValid(p,n,ROUTE_KEY,FLEET_ID)){++rejectCount;return;}
 if((ROLE==1&&p[3]==secure::HELLO)||(ROLE==3&&p[3]==secure::HELLO_ACK&&p[9]+1==p[7]&&secure::forNode(p,NODE_ID))){helloPacket(p,n,now);return;}
 if(ROLE==3){
  if(!secure::forNode(p,NODE_ID)||duplicate(p,now)){++rejectCount;return;}
  if(secure::advance(p,n,NODE_ID,ROUTE_KEY)&&queuePacket(p,n,p[3],12+(esp_random()%65))){++rxCount;nodeForwardAt=now;}
  return;
 }
 if(p[3]>=secure::HELLO){return;}
 uint8_t id=p[6];
 if(ROLE==1?(!secure::atBase(p)||id!=selected||p[3]!=mission::RESPONSE):
  (id!=ROVER_ID||p[3]==mission::RESPONSE||(!secure::discovering(p)&&!secure::atRover(p)))){++rejectCount;return;}
 if(duplicate(p,now)){++rejectCount;return;}
 uint8_t key[32],body[mission::MAX_PLAIN];
 if(!keyFor(id,key)||!secure::open(p,n,body,key)){memset(key,0,32);++rejectCount;return;}memset(key,0,32);
 size_t len=mission::u16(p+10);++rxCount;
 if(ROLE==1){
  if(len<41||!mission::equal(body,baseQuery.token,16)||uint32_t(now-baseQuery.at)>mission::TOKEN_MS){++rejectCount;return;}
  if(!roverIdentity[id-1].observe(fleet::readId(body+32),now)){clearCommands();status("ROVER ID_CONFLICT; commands blocked until conflict expires");++rejectCount;return;}
  if(!waiting||!baseQuery.consume(body,now)){++rejectCount;return;}
  waiting=false;
  for(unsigned i=0;i<p[7];++i)if(nodeIdentity[p[14+i]-1].conflict){clearCommands();status("NODE ID_CONFLICT on route; commands blocked");++rejectCount;return;}
  remoteToken.issue(body+16,now);pathCount=p[7];memcpy(path,p+14,pathCount);
  size_t mavLen=body[40];if(len!=41+mavLen||mavLen>mission::MAX_MAV){++rejectCount;return;}
  size_t cursor=0;mission::Mav frames[4];unsigned count=0;
  while(cursor<mavLen&&count<4){
   auto*q=body+41+cursor;if(mavLen-cursor<2||(q[0]!=0xfe&&q[0]!=0xfd)){++rejectCount;return;}
   size_t frameLen=q[1]+(q[0]==0xfd?12:8);
   if(frameLen>mavLen-cursor||!frames[count].parse(q,frameLen)||frames[count].sys!=selected||frames[count].comp!=1){++rejectCount;return;}
   cursor+=frameLen;++count;
  }
  if(cursor!=mavLen){++rejectCount;return;}
  for(unsigned i=0;i<count;++i)usbOut(selected,1,frames[i].bytes,frames[i].n);
  char msg[64];snprintf(msg,sizeof(msg),"ROVER %u route=%u telemetry=%u",selected,pathCount,unsigned(mavLen));status(msg);
  if(selected!=owner||!Serial||uint32_t(now-hostAt)>mission::HOST_MS){clearCommands();nextPoll=now+150;return;}
  mission::Frame cmd;bool haveCommand=false;mission::Mav first;
  if(commands[0].fresh(now)&&first.parse(commands[0].data,commands[0].n)&&holdFrame(first,selected)){
   cmd=commands[0];commands[0].clear();haveCommand=true;servedHostHeartbeat=false;
  }
  if(!haveCommand&&!servedHostHeartbeat&&heartbeat.fresh(now)){cmd=heartbeat;heartbeat.clear();haveCommand=servedHostHeartbeat=true;}
  if(!haveCommand&&takeFrame(commands,4,cmd,now,mission::HOST_MS)){haveCommand=true;servedHostHeartbeat=false;}
  if(!haveCommand&&heartbeat.fresh(now)){cmd=heartbeat;heartbeat.clear();haveCommand=servedHostHeartbeat=true;}
  if(haveCommand){
   uint8_t down[mission::MAX_PLAIN];memcpy(down,remoteToken.token,16);down[16]=cmd.n;memcpy(down+17,cmd.data,cmd.n);
   remoteToken.active=false;if(!makePacket(mission::DATA,selected,down,17+cmd.n,path,pathCount))++dropCount;
  }
  nextPoll=now+150;return;
 }
 if(p[3]==mission::SYNC){
  if(len!=16){++rejectCount;return;}
  uint8_t response[mission::MAX_PLAIN];memcpy(response,body,16);esp_fill_random(response+16,16);fleet::writeId(response+32,ESP.getEfuseMac());
  size_t used=0;unsigned packed=0;
  auto append=[&](mission::Frame&s,uint32_t ttl){
   if(!s.n)return false;if(!s.fresh(now,ttl)){s.clear();++dropCount;return false;}
   if(packed>=4||used+s.n>mission::MAX_MAV)return false;
   memcpy(response+41+used,s.data,s.n);used+=s.n;++packed;s.clear();return true;
  };
  append(fcHeartbeat,1500);
  for(unsigned i=0;i<4;++i){unsigned slot=(criticalCursor+i)%4;if(append(telemetry[slot],1800)){criticalCursor=(slot+1)%4;break;}}
  const unsigned start=navCursor;for(unsigned i=0;i<4;++i){unsigned slot=(start+i)%4;if(append(telemetry[4+slot],1800))navCursor=(slot+1)%4;}
  response[40]=used;
  if(makePacket(mission::RESPONSE,ROVER_ID,response,41+used,p+14,p[7])){
   remoteToken.issue(response+16,now);pathCount=p[7];memcpy(path,p+14,pathCount);
  }
 }else if(p[3]==mission::DATA){
  if(p[7]!=pathCount||!mission::equal(p+14,path,pathCount)||len<17||len!=size_t(17+body[16])||body[16]>mission::MAX_MAV||!remoteToken.consume(body,now)){++rejectCount;return;}
  mission::Mav frame;if(!frame.parse(body+17,body[16])){++rejectCount;return;}
  mission::Gate next=gate;
  if(!next.down(frame,now,SERVO_MASK)||fc.availableForWrite()<int(frame.n)){++rejectCount;return;}
  if(fc.write(frame.bytes,frame.n)==frame.n)gate=next;else{gate.invalidate();++dropCount;}
 }
}
void startTx(){
 uint32_t now=millis();if(!pending.n)return;
 if(uint32_t(now-pending.at)>500){pending.n=0;++dropCount;receiveMode();return;}
 irq=false;txLimit=(radio.getTimeOnAir(pending.n)+999)/1000+100;txAt=now;uint8_t kind=pending.kind;
 int s=radio.startTransmit(pending.bytes,pending.n);pending.n=0;
 if(s!=RADIOLIB_ERR_NONE){fault();return;}transmitting=true;++txCount;
 if(ROLE==1&&kind==mission::SYNC){waiting=true;baseQuery.at=now;}
}
void pumpRadio(){
 if(!running)return;uint32_t now=millis();
 if(transmitting){
  if(irq||uint32_t(now-txAt)>txLimit){
   if(!(radio.getIrqFlags()&RADIOLIB_SX126X_IRQ_TX_DONE)){fault();return;}
   irq=false;int s=radio.finishTransmit();transmitting=false;if(s!=RADIOLIB_ERR_NONE){fault();return;}receiveMode();
  }
  return;
 }
 if(scanning){
  if(irq){irq=false;scanning=false;int s=radio.getChannelScanResult();
   if(s==RADIOLIB_CHANNEL_FREE)startTx();
   else if(s==RADIOLIB_LORA_DETECTED){pending.due=now+20+(esp_random()%100);receiveMode();}
   else fault();
  }else if(uint32_t(now-txAt)>100){scanning=false;pending.n=0;++dropCount;receiveMode();}return;
 }
 if(irq){
  irq=false;uint8_t packet[secure::MAX];size_t n=radio.getPacketLength();
  if(n>sizeof(packet)||n<secure::HEAD+secure::NONCE+secure::TAG+secure::MAC){radio.standby();receiveMode();++rejectCount;}
  else{int s=radio.readData(packet,n);if(!receiveMode())return;if(s==RADIOLIB_ERR_NONE)onPacket(packet,n);else ++rejectCount;}
 }
 if(pending.n&&int32_t(now-pending.due)>=0){
  if(uint32_t(now-pending.at)>500){pending.n=0;++dropCount;return;}
  irq=false;txAt=now;int s=radio.startChannelScan();if(s!=RADIOLIB_ERR_NONE){fault();return;}scanning=true;
 }else if(!pending.n&&uint32_t(now-rxAt)>5000)receiveMode();
}
// WATCH is host configuration, never RF command data. Atomic parse, no board list.
bool setWatch(const uint8_t*p,size_t n){
 if(n<7||n>80||memcmp(p,"WATCH:",6))return false;
 uint8_t temp[secure::MAX_ROVERS];unsigned count=0,value=0;bool digits=false;
 for(size_t i=6;i<=n;++i){
  uint8_t c=i<n?p[i]:',';
  if(c>='0'&&c<='9'){value=value*10+c-'0';digits=true;if(value>secure::MAX_ROVERS)return false;}
  else if(c==','){
   if(!digits||!value||count>=secure::MAX_ROVERS)return false;
   for(unsigned j=0;j<count;++j)if(temp[j]==value)return false;
   temp[count++]=value;value=0;digits=false;
  }else return false;
 }
 memcpy(watch,temp,count);watchCount=count;watchCursor=0;return true;
}
void pumpUsb(){
 uint32_t now=millis();
 for(unsigned i=0;i<512&&Serial.available();++i)if(usbParser.feed(Serial.read(),now)){
  auto p=usbParser.buf;uint8_t id=p[2];size_t n=mission::u16(p+4);mission::Mav frame;
  if(!id||id>secure::MAX_ROVERS){++rejectCount;continue;}
  if(p[3]==3&&n==4&&!memcmp(p+6,"INFO",4)){
   const char*caps="TFM1;fw=1.1.0-dev1;maxhops=4;rovers=20;writer=1;watch=1";
   usbOut(id,3,reinterpret_cast<const uint8_t*>(caps),strlen(caps));continue;
  }
  if(p[3]==4){const char*msg=setWatch(p+6,n)?"WATCH_OK":"WATCH_REJECT";usbOut(id,4,reinterpret_cast<const uint8_t*>(msg),strlen(msg));continue;}
  if(p[3]!=1||!frame.parse(p+6,n)||frame.sys!=255||frame.comp!=190){++rejectCount;continue;}
  if(owner!=id){
   if(owner&&uint32_t(now-hostAt)<5000){status("WRITER_BUSY; wait 5s after stopping old host");++rejectCount;continue;}
   if(transmitting||scanning||pending.n){++rejectCount;continue;}
   clearCommands();waiting=false;baseQuery.active=false;owner=id;selected=id;nextPoll=now;
  }
  hostAt=now;
  if(holdFrame(frame,id)){
   clearCommands();
   if(!transmitting&&pending.kind==mission::DATA){pending.n=0;if(scanning){radio.standby();scanning=false;receiveMode();}}
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
  else if(frame.id==40||frame.id==51||frame.id==44||frame.id==39||frame.id==73||frame.id==47||frame.id==77||frame.id==22)pushFrame(telemetry,4,frame.bytes,frame.n,now);
  else if(frame.id==24||frame.id==33||frame.id==42||frame.id==46||frame.id==253){
   bool replaced=false;for(unsigned j=4;j<8;++j){auto&s=telemetry[j];if(s.n){mission::Mav old;if(old.parse(s.data,s.n)&&old.id==frame.id){s.set(frame.bytes,frame.n,now);replaced=true;break;}}}
   if(!replaced)pushFrame(telemetry+4,4,frame.bytes,frame.n,now);
  }
 }
}
void poll(){
 uint32_t now=millis();if(transmitting||scanning||pending.n)return;
 if(!Serial){clearCommands();waiting=false;baseQuery.active=false;return;}
 if(waiting){if(uint32_t(now-baseQuery.at)<=mission::TOKEN_MS)return;waiting=false;baseQuery.active=false;++dropCount;}
 if(int32_t(now-nextPoll)<0)return;
 if(owner&&uint32_t(now-hostAt)<5000)selected=owner;
 else{clearCommands();owner=0;selected=watch[watchCursor++%watchCount];}
 uint8_t query[16];esp_fill_random(query,16);baseQuery.issue(query,now);
 if(!makePacket(mission::SYNC,selected,query,16))baseQuery.active=false;
 nextPoll=now+150;
}
void nodeHello(){
 uint32_t now=millis();if(nodeReady&&uint32_t(now-nodeReadyAt)>45000)nodeReady=false;
 if(pending.n||transmitting||scanning||int32_t(now-nextHello)<0)return;
 nextHello=now+15000+(esp_random()%5000);
 uint8_t body[25],route[]={NODE_ID},packet[secure::MAX];esp_fill_random(body,16);fleet::writeId(body+16,ESP.getEfuseMac());body[24]=NODE_ID;
 size_t n=secure::seal(packet,secure::HELLO,FLEET_ID,0,route,1,body,sizeof(body),ROUTE_KEY,ROUTE_KEY);
 if(n&&queuePacket(packet,n,secure::HELLO,10+(esp_random()%100)))nodeQuery.issue(body,now);
}
void display(){
 uint32_t now=millis();static bool button=false;bool pressed=digitalRead(0)==LOW;
 if(pressed&&!button){wakeAt=now;oled.setAwake(true);}button=pressed;
 if(uint32_t(now-wakeAt)>=30000&&!oled.asleep)oled.setAwake(false);
 if(uint32_t(now-displayAt)>=1000){
  displayAt=now;char row0[24],row1[24],row2[24],row3[24],row4[24],row5[24];
  snprintf(row0,sizeof(row0),"FLEET 1.1.0 DEV1");snprintf(row1,sizeof(row1),"%s ID %u",ROLE==1?"BASE":ROLE==2?"ROVER":"NODE",ROLE==1?selected:ROLE==2?ROVER_ID:NODE_ID);
  snprintf(row2,sizeof(row2),"RF %s %.1f MHZ",running?"OK":"OFF",double(FREQUENCY_MHZ));
  snprintf(row3,sizeof(row3),"RX %lu TX %lu",(unsigned long)(rxCount%100000),(unsigned long)(txCount%100000));
  snprintf(row4,sizeof(row4),"REJ %lu DROP %lu",(unsigned long)(rejectCount%100000),(unsigned long)(dropCount%100000));
  snprintf(row5,sizeof(row5),"%s",ROLE==2?(gate.fresh(now)?(gate.armed?"FC ARMED":"FC DISARMED"):"WAIT FC"):ROLE==3?(nodeForwardAt&&uint32_t(now-nodeForwardAt)<3000?"FORWARDING":nodeReady?"READY / STANDBY":"SEARCH BASE"):"ONE MISSION WRITER");
  const char*rows[]={row0,row1,row2,row3,row4,row5,"BOOT WAKES DISPLAY","NO AUTO ARM"};oled.rows(rows);
 }
 oled.step();digitalWrite(37,running?(uint32_t(now%1000)<(rxCount?80:400)):((now/150)%2));
}
bool initRadio(){
 radio.standby();SPI.begin(5,3,6,7);
 if(radio.begin(FREQUENCY_MHZ,250.0,7,5,0x12,POWER_DBM,8,1.6)!=RADIOLIB_ERR_NONE)return false;
 if(radio.setRxBoostedGainMode(true,true)!=RADIOLIB_ERR_NONE)return false;
 radio.setDio1Action(radioInterrupt);running=true;return receiveMode();
}
void setup(){
 bootloader_random_enable();Serial.begin(115200);Serial.setTxTimeoutMs(1);pinMode(0,INPUT_PULLUP);pinMode(37,OUTPUT);oled.begin();wakeAt=millis();
 for(unsigned i=0;i<secure::MAX_ROVERS;++i)watch[i]=i+1;
 if(!PROVISIONED||!keySet(ROUTE_KEY)){stopped=true;return;}
#if ROLE != 3
 if(!keySet(ENDPOINT_ROOT)){stopped=true;return;}
#endif
 if(ROLE==2){fc.setRxBufferSize(2048);fc.setTxBufferSize(512);fc.begin(115200,SERIAL_8N1,44,43);}
 nextHello=millis()+1000+(esp_random()%4000);
 if(!initRadio())fault();
}
void loop(){
 if(!stopped&&!running&&int32_t(millis()-recoveryAt)>=0){if(!initRadio())recoveryAt=millis()+2000;}
 if(ROLE==1&&!Serial){clearCommands();waiting=false;baseQuery.active=false;owner=0;if(!transmitting&&!scanning)pending.n=0;}
 if(ROLE==1)pumpUsb();if(ROLE==2)pumpFc();pumpRadio();
 if(running){if(ROLE==1)poll();if(ROLE==3)nodeHello();}
 if(ROLE==1&&millis()-diagAt>10000){diagAt=millis();status(running?"FLEET_DEV; discovery active; FC heartbeat proves vehicle connectivity":"RF OFF; check provisioning/radio");}
 display();delay(1);
}
