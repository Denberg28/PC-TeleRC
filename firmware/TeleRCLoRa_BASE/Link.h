#pragma once
// TeleRC SX1262 ArduRover direct pair 0.2.1. No Wi-Fi in the driving path.
#include <Arduino.h>
#include <algorithm>
#include <cctype>
#include <SPI.h>
#include <RadioLib.h>
#include <Preferences.h>
#include <esp_system.h>
#include "MeshCore.h"

constexpr uint8_t BASE=1, ROVER=3;
static_assert(TELERC_ROLE==BASE || TELERC_ROLE==ROVER, "Select BASE or ROVER");
struct Config {
 uint32_t magic=0x544c0200, khz=0;
 uint8_t power=2, key[32]={};
};
Config cfg;
SX1262 radio=new Module(7,33,8,34);
HardwareSerial vehicle(1);
mesh::Seen seen;
mesh::Challenge challenge;
mesh::Safety safety;
mesh::MavParser mav;
telerc::CommandMailbox commands;
telerc::UartParser usbParser;
bool maintenance=false,radioOK=false,transmitting=false,scanning=false,pollInFlight=false;
bool haveFc=false,stopPending=false,bootTracking=false;
uint32_t bootPressAt=0;
volatile bool radioIRQ=false;
uint64_t inflightToken=0;
uint32_t txAt=0,pollAt=0,fcAt=0,lastStopTry=0,scanAt=0,bootId=0;
uint32_t rxCount=0,rejectCount=0,txFail=0,uartDrops=0,stopCount=0;
uint8_t lastReason=0;
size_t scanSlot=0;
struct Telemetry {uint8_t data[telerc::RADIO_MAX]={};size_t n=0;uint32_t at=0;};
Telemetry telemetry[4];
struct TxSlot {mesh::Packet p;bool active=false;uint32_t at=0,due=0;};
TxSlot queue[4];
// CDC is nonblocking; complete framed messages are queued and written in chunks.
struct UsbSlot {uint8_t data[telerc::UART_MAX+6]={};size_t n=0,offset=0;uint32_t at=0;bool expires=false;};
UsbSlot usbQueue[8];
uint8_t usbHead=0,usbTail=0,usbCount=0;

void IRAM_ATTR onRadio(){radioIRQ=true;}
bool validConfig(const Config&v){
 uint8_t key=0;for(auto b:v.key)key|=b;
 bool band=(v.khz>=400250&&v.khz<=519750)||(v.khz>=830250&&v.khz<=944750);
 return v.magic==0x544c0200&&band&&key&&v.power>=2&&v.power<=17;
}
bool usbSend(const uint8_t*p,size_t n,bool expires=false){
 if(usbCount==8){++uartDrops;return false;}
 auto&s=usbQueue[usbTail];s.n=telerc::encodeUart(p,n,s.data);s.offset=0;s.at=millis();s.expires=expires;
 if(!s.n)return false;
 usbTail=(usbTail+1)%8;++usbCount;return true;
}
void usbText(const char*s,bool expires=false){usbSend(reinterpret_cast<const uint8_t*>(s),strlen(s),expires);}
void serviceUsbTx(){
 if(!usbCount)return;
 auto&s=usbQueue[usbHead];
 if(s.expires&&uint32_t(millis()-s.at)>200){usbHead=(usbHead+1)%8;--usbCount;return;}
 int capacity=Serial.availableForWrite();
 if(capacity<=0)return;
 size_t count=std::min(s.n-s.offset,size_t(capacity));
 size_t written=Serial.write(s.data+s.offset,count);
 if(written>count){++uartDrops;return;}
 s.offset+=written;
 if(s.offset==s.n){usbHead=(usbHead+1)%8;--usbCount;}
}
void info(){
 char line[180];
 uint16_t fingerprint=telerc::crc16(cfg.key,sizeof(cfg.key));
 snprintf(line,sizeof(line),"TELERC_LORA_INFO_V2,%s,1262,%u,%lu,%u,%04x,%lu,%lu,%lu,%lu,ARDUROVER",
   TELERC_ROLE==BASE?"BASE":"ROVER",unsigned(radioOK&&!maintenance),
   static_cast<unsigned long>(cfg.khz),unsigned(cfg.power),unsigned(fingerprint),
   static_cast<unsigned long>(rxCount),static_cast<unsigned long>(rejectCount),
   static_cast<unsigned long>(txFail),static_cast<unsigned long>(uartDrops));
 usbText(line);
}
bool parseNumber(const char*s,uint32_t low,uint32_t high,uint32_t&v){
 if(!*s||strlen(s)>9)return false;
 v=0;for(;*s;++s){if(*s<'0'||*s>'9')return false;v=v*10+uint32_t(*s-'0');}
 return v>=low&&v<=high;
}
void provision(const uint8_t*p,size_t n){
 if(radioOK&&!maintenance){usbText("TELERC_LORA_RESULT_V1,ACTIVE_DISCONNECT_AND_ERASE_NVS_FIRST");return;}
 char text[140];if(n>=sizeof(text)||memchr(p,0,n)){usbText("TELERC_LORA_RESULT_V1,INVALID");return;}
 memcpy(text,p,n);text[n]=0;
 char*parts[4]={};size_t k=0;char*save=nullptr;
 for(char*t=strtok_r(text,",",&save);t&&k<4;t=strtok_r(nullptr,",",&save))parts[k++]=t;
 Config next;uint32_t power=0;
 size_t commas=0;for(size_t i=0;i<n;++i)commas+=p[i]==',';
 bool ok=commas==3&&k==4&&strcmp(parts[0],"TELERC_LORA_SET_V1")==0&&
   parseNumber(parts[1],400250,944750,next.khz)&&parseNumber(parts[2],2,17,power)&&strlen(parts[3])==64;
 if(ok){
  next.power=uint8_t(power);
  for(int i=0;i<32;++i){
   char pair[3]={parts[3][2*i],parts[3][2*i+1],0};
   if(!isxdigit(pair[0])||!isxdigit(pair[1])){ok=false;break;}
   next.key[i]=uint8_t(strtoul(pair,nullptr,16));
  }
 }
 if(!ok||!validConfig(next)){usbText("TELERC_LORA_RESULT_V1,INVALID");return;}
 Preferences pref;
 if(!pref.begin("telerc-lora2",false)){usbText("TELERC_LORA_RESULT_V1,STORAGE_FAILED");return;}
 bool stored=pref.putBytes("config",&next,sizeof(next))==sizeof(next);pref.end();
 // RF stays OFF until a physical restart; no provisioning-triggered motion.
 if(stored)cfg=next;
 usbText(stored?"TELERC_LORA_RESULT_V1,SAVED_RESTART_BOARD":"TELERC_LORA_RESULT_V1,STORAGE_FAILED");
}
bool freshFc(uint32_t now){return haveFc&&uint32_t(now-fcAt)<2500;}
void clearQueue(){for(auto&s:queue)s.active=false;}
bool enqueue(const mesh::Packet&p,uint32_t jitter){
 uint32_t now=millis();
 for(auto&s:queue)if(!s.active||uint32_t(now-s.at)>mesh::QUEUE_MS){s.p=p;s.at=now;s.due=now+jitter;s.active=true;return true;}
 ++txFail;return false;
}
mesh::Packet makePacket(uint8_t kind,uint64_t token){
 mesh::Packet p;p.kind=kind;p.network=1;p.origin=TELERC_ROLE==BASE?1:2;p.sender=p.origin;
 p.dest=kind==mesh::POLL?1:2;p.limit=p.hops=1;p.token=token;
 if(kind==mesh::POLL){p.ready=safety.ready;p.owned=safety.owned;p.reason=lastReason;
  p.stops=stopCount;p.boot=bootId;p.age=safety.owned?uint32_t(millis()-safety.at[0]):0;}
 return p;
}
bool uartWrite(const uint8_t*p,size_t n){
 if(!n)return true;
 if(vehicle.availableForWrite()<int(n)||vehicle.write(p,n)!=n){++uartDrops;return false;}return true;
}
void makeRc(uint8_t*out,uint16_t value,uint8_t seq){
 memset(out,0,26);out[0]=0xfe;out[1]=18;out[2]=seq;out[3]=255;out[4]=190;out[5]=70;
 for(int i=0;i<8;++i)mesh::put16(out+6+2*i,i<2?value:65535);
 out[22]=1;out[23]=1;telerc::CommandMailbox::checksumRc(out);
}
void tryStop(){
 if(!stopPending)return;
 uint8_t out[52];makeRc(out,1500,0);makeRc(out+26,0,1);
 if(uartWrite(out,sizeof(out)))stopPending=false;
 lastStopTry=millis();
}
// Reasons: 0 boot, 1 command loss, 2 FC loss, 3 explicit release,
// 4 disconnect, 5 UART failure, 6 radio fault, 7 disarm.
void stopControl(uint8_t reason){
 if(safety.owned){stopPending=true;++stopCount;lastReason=reason;}
 safety.latch();challenge.active=false;commands.clear();clearQueue();tryStop();
}
bool restartRx(){
 radioIRQ=false;
 if(radio.startReceive()!=RADIOLIB_ERR_NONE){radioOK=false;stopControl(6);return false;}return true;
}
void radioFault(){++txFail;radioOK=false;transmitting=scanning=false;radio.standby();stopControl(6);}
void pumpTx(){
 if(!radioOK||transmitting||scanning)return;
 uint32_t now=millis();
 for(auto&s:queue){
  if(!s.active)continue;
  if(uint32_t(now-s.at)>mesh::QUEUE_MS){s.active=false;++txFail;continue;}
  if(int32_t(now-s.due)<0)continue;
  radioIRQ=false;
  if(radio.startChannelScan()!=RADIOLIB_ERR_NONE){radioFault();return;}
  scanSlot=size_t(&s-queue);scanAt=now;scanning=true;return;
 }
}
void forwardStatus(const mesh::Packet&p){
 char line[160];snprintf(line,sizeof(line),"TELERC_LORA_STATUS_V1,%u,%u,%lu,%lu,%u,%lu",
  unsigned(p.ready),unsigned(p.owned),static_cast<unsigned long>(p.stops),
  static_cast<unsigned long>(p.boot),unsigned(p.reason),static_cast<unsigned long>(p.age));
 usbText(line,true);
}
void acceptCommands(const uint8_t*p,size_t n){
 uint32_t now=millis();
 if(!telerc::validBundle(p,n)){++rejectCount;return;}
 mesh::Safety next=safety;telerc::CommandMailbox check;
 uint8_t out[telerc::RADIO_MAX];size_t used=0;bool requestedStop=false;uint8_t stopReason=3;
 for(size_t i=0;i<n;){size_t k=p[i++];const uint8_t*f=p+i;i+=k;
  if(!check.accept(f,k,now)){++rejectCount;return;}
  if(telerc::textEquals(f,k,"TELERC_DISCOVER_V1"))continue;
  if(telerc::textEquals(f,k,"TELERC_DISCONNECT_V1")){stopControl(4);return;}
  if(telerc::mavV1(f,k,70,18,124)){
   if(mesh::u16(f+6)==0||mesh::u16(f+8)==0){requestedStop=true;next.latch();continue;}
   if(stopPending||!freshFc(now)||!next.rc(f,k,now)){++rejectCount;return;}
  }
  if(telerc::mavV1(f,k,76,33,152)){
   if(f[8]==0x80&&f[9]==0x3f){if(!freshFc(now)||!next.centered(now)){++rejectCount;return;}}
   else {requestedStop=true;stopReason=7;next.latch();}
  }
  memcpy(out+used,f,k);used+=k;
 }
 if(requestedStop)stopControl(stopReason);
 if(uartWrite(out,used))safety=next;else stopControl(5);
}
void pumpRadio(){
 if(!radioOK)return;
 uint32_t now=millis();
 if(scanning){
  if(radioIRQ){
   radioIRQ=false;scanning=false;int state=radio.getChannelScanResult();auto&s=queue[scanSlot];
   if(state==RADIOLIB_LORA_DETECTED){s.due=now+8+(esp_random()%18);restartRx();return;}
   if(state!=RADIOLIB_CHANNEL_FREE){radioFault();return;}
   if(!s.active||uint32_t(now-s.at)>mesh::QUEUE_MS){s.active=false;++txFail;restartRx();return;}
   uint8_t out[mesh::MAX];size_t n=mesh::seal(s.p,cfg.key,out);auto p=s.p;s.active=false;
   if(!n){++rejectCount;restartRx();return;}
   if(p.kind==mesh::COMMAND&&uint32_t(millis()-s.at)+(radio.getTimeOnAir(n)+999)/1000+2>mesh::timing(1).responseMs){
    ++txFail;restartRx();return;
   }
   if(radio.startTransmit(out,n)!=RADIOLIB_ERR_NONE){radioFault();return;}
   transmitting=true;txAt=now;pollInFlight=p.kind==mesh::POLL&&TELERC_ROLE==ROVER;inflightToken=p.token;
  }else if(uint32_t(now-scanAt)>20)radioFault();
  return;
 }
 if(transmitting){
  if(radioIRQ){radioIRQ=false;radio.finishTransmit();transmitting=false;
   if(pollInFlight){challenge.issue(inflightToken,millis(),mesh::timing(1).responseMs);pollAt=millis();}
   pollInFlight=false;restartRx();
  }else if(uint32_t(now-txAt)>100)radioFault();
  return;
 }
 if(!radioIRQ)return;
 radioIRQ=false;uint8_t in[mesh::MAX];size_t n=radio.getPacketLength();
 if(n<mesh::HEADER+mesh::TAG||n>sizeof(in)){radio.standby();restartRx();++rejectCount;return;}
 int state=radio.readData(in,n);if(!restartRx())return;
 mesh::Packet p;
 if(state!=RADIOLIB_ERR_NONE||!mesh::open(in,n,cfg.key,p)||p.network!=1||p.limit!=1||p.hops!=1||
    (TELERC_ROLE==BASE?(p.kind!=mesh::POLL||p.origin!=2||p.sender!=2||p.dest!=1):
                      (p.kind!=mesh::COMMAND||p.origin!=1||p.sender!=1||p.dest!=2))){++rejectCount;return;}
 if(!seen.admit(p,now)){++rejectCount;return;}++rxCount;
 if(TELERC_ROLE==BASE){
  forwardStatus(p);
  if(p.n&&mesh::telemetryClass(p.body,p.n)>=0)usbSend(p.body,p.n,true);
  mesh::Packet response=makePacket(mesh::COMMAND,p.token);response.n=commands.take(response.body,millis());enqueue(response,3);
 }else{
  if(!challenge.consume(p.token,now)){++rejectCount;return;}
  acceptCommands(p.body,p.n);
 }
}
void pumpUsb(){
 for(int i=0;i<512&&Serial.available();++i){
  if(!usbParser.feed(uint8_t(Serial.read()),millis()))continue;
  const uint8_t*p=usbParser.data+4;size_t n=usbParser.length();
  if(telerc::textEquals(p,n,"TELERC_LORA_GET_V1")){info();continue;}
  if(n>=19&&memcmp(p,"TELERC_LORA_SET_V1,",19)==0){provision(p,n);continue;}
  if(TELERC_ROLE==BASE&&radioOK&&!maintenance){if(!commands.accept(p,n,millis()))++rejectCount;}
  else ++rejectCount;
 }
}
void pumpVehicle(){
 for(size_t i=0;i<512&&vehicle.available();++i){
  if(!mav.feed(uint8_t(vehicle.read()),millis()))continue;
  int slot=mesh::telemetryClass(mav.data,mav.total);
  if(slot<0||mav.total>telerc::RADIO_MAX)continue;
  auto&s=telemetry[slot];memcpy(s.data,mav.data,mav.total);s.n=mav.total;s.at=millis();
  if(slot==1){fcAt=millis();haveFc=true;}
 }
}
void sendPoll(){
 uint32_t now=millis();
 if(transmitting||scanning||challenge.pending(now)||uint32_t(now-pollAt)<mesh::timing(1).pollMs)return;
 for(auto&s:queue)if(s.active)return;
 uint64_t token=0;while(!token)token=(uint64_t(esp_random())<<32)|esp_random();
 mesh::Packet p=makePacket(mesh::POLL,token);
 // ACK and heartbeat before optional telemetry. Each poll always carries status.
 for(auto&s:telemetry)if(s.n){size_t n=s.n;s.n=0;if(uint32_t(now-s.at)>1200)continue;p.n=n;memcpy(p.body,s.data,n);break;}
 challenge.active=false;if(enqueue(p,0))pollAt=now;
}
void setup(){
 Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT
 Serial.setTxTimeoutMs(1);
#endif
 pinMode(0,INPUT_PULLUP);delay(30);
 do {bootId=esp_random();}while(!bootId);
 Preferences pref;if(pref.begin("telerc-lora2",true)){
  Config stored;if(pref.getBytesLength("config")==sizeof(stored)&&pref.getBytes("config",&stored,sizeof(stored))==sizeof(stored)&&validConfig(stored))cfg=stored;pref.end();
 }
 maintenance=!validConfig(cfg)||digitalRead(0)==LOW;
 if(maintenance)return;
 if(TELERC_ROLE==ROVER){vehicle.setRxBufferSize(1024);vehicle.setTxBufferSize(1024);vehicle.begin(115200,SERIAL_8N1,44,43);}
 SPI.begin(5,3,6,7);
 int state=radio.begin(cfg.khz/1000.0f,500.0,7,5,0x12,cfg.power,8,1.6);
 if(state!=RADIOLIB_ERR_NONE){++txFail;return;}
 if(radio.setRxBoostedGainMode(true,true)!=RADIOLIB_ERR_NONE){++txFail;return;}
 radio.setDio1Action(onRadio);radioOK=true;restartRx();
}
void loop(){
 uint32_t now=millis();
 // Enter setup by holding BOOT after the sketch has booted; holding it during
 // RESET selects the ESP ROM downloader instead. Never resume RF automatically.
 if(!maintenance&&digitalRead(0)==LOW){
  if(!bootTracking){bootTracking=true;bootPressAt=now;}
  else if(uint32_t(now-bootPressAt)>=1000){
   stopControl(4);radio.standby();radioOK=false;transmitting=scanning=false;maintenance=true;
  }
 }else bootTracking=false;
 if(TELERC_ROLE==ROVER&&stopPending&&uint32_t(now-lastStopTry)>=100)tryStop();
 if(TELERC_ROLE==ROVER&&!maintenance){
  if(safety.expired(now))stopControl(1);
  else if(safety.owned&&!freshFc(now))stopControl(2);
  pumpVehicle();
 }
 pumpUsb();pumpRadio();
 if(radioOK&&TELERC_ROLE==ROVER)sendPoll();
 pumpTx();serviceUsbTx();delay(1);
}

