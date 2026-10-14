#include <cassert>
#include <iostream>
#include "Link.h"

void resetHost(){
 safety={};commands={};challenge={};seen={};mav={};usbParser={};
 Serial.rx.clear();Serial.tx.clear();Serial.cursor=0;Serial.capacity=1024;
 vehicle.rx.clear();vehicle.tx.clear();vehicle.cursor=0;vehicle.capacity=1024;
 radio.tx.clear();radio.rx.clear();radio.result=0;radio.receiveResult=0;
 radio.scanResult=RADIOLIB_CHANNEL_FREE;
 usbHead=usbTail=usbCount=0;clearQueue();
 radioOK=true;maintenance=false;transmitting=scanning=pollInFlight=false;
 stopPending=false;bootTracking=false;pins[0]=HIGH;haveFc=true;fcAt=testMs;stopCount=0;lastReason=0;
 bootId=123;cfg=Config{};cfg.khz=915000;for(auto&b:cfg.key)b=0x12;
}
std::vector<uint8_t> rc(uint16_t steer,uint16_t drive){
 uint8_t p[26];makeRc(p,1500,4);mesh::put16(p+6,steer);mesh::put16(p+8,drive);
 telerc::CommandMailbox::checksumRc(p);return {p,p+26};
}
void accept(const std::vector<uint8_t>&p){
 std::vector<uint8_t> bundle{uint8_t(p.size())};bundle.insert(bundle.end(),p.begin(),p.end());
 acceptCommands(bundle.data(),bundle.size());
}
void inputUsb(const char*s){
 uint8_t out[telerc::UART_MAX+6];size_t n=telerc::encodeUart(reinterpret_cast<const uint8_t*>(s),strlen(s),out);
 Serial.rx.insert(Serial.rx.end(),out,out+n);pumpUsb();
}
void drainUsb(){while(usbCount)serviceUsbTx();}
std::vector<std::string> usbMessages(){
 drainUsb();telerc::UartParser parser;std::vector<std::string> result;
 for(auto b:Serial.tx)if(parser.feed(b,testMs))result.emplace_back(reinterpret_cast<char*>(parser.data+4),parser.length());
 return result;
}
int main(){
 resetHost();maintenance=true;radioOK=false;cfg=Config{};
 inputUsb("TELERC_LORA_GET_V1");auto messages=usbMessages();
 assert(messages.size()==1&&messages[0].find("TELERC_LORA_INFO_V2,")==0);
 assert(messages[0].find(",ARDUROVER")!=std::string::npos);
 std::string request="TELERC_LORA_SET_V1,915000,2,"+std::string(64,'1');
 inputUsb(request.c_str());messages=usbMessages();
 assert(messages.back()=="TELERC_LORA_RESULT_V1,SAVED_RESTART_BOARD");
 assert(validConfig(cfg)&&!radioOK&&maintenance);
 inputUsb((request+",extra").c_str());assert(usbMessages().back()=="TELERC_LORA_RESULT_V1,INVALID");
 resetHost();inputUsb(request.c_str());
 assert(usbMessages().back()=="TELERC_LORA_RESULT_V1,ACTIVE_DISCONNECT_AND_ERASE_NVS_FIRST");
 // Production setup loads saved config; holds BOOT for local re-provisioning.
 pins[0]=HIGH;setup();assert(radioOK&&!maintenance);
 pins[0]=LOW;setup();assert(maintenance);pins[0]=HIGH;

 resetHost();accept(rc(1700,1800));assert(!safety.owned&&vehicle.tx.empty());
 accept(rc(1500,1500));assert(safety.ready&&safety.owned==3);
 accept(rc(1700,1800));assert(safety.value[0]==1700&&safety.value[1]==1800);
 auto packet=rc(1500,1500);mesh::put16(packet.data()+16,1800);telerc::CommandMailbox::checksumRc(packet.data());
 size_t before=vehicle.tx.size();accept(packet);assert(vehicle.tx.size()==before); // CH6 takeover protected
 for(int i=0;i<2000;++i){testMs+=100;fcAt=testMs;accept(rc(i%2?1000:2000,i%2?2000:1000));assert(safety.owned==3);}
 testMs+=500;fcAt=testMs;
 if(TELERC_ROLE==ROVER){loop();assert(!safety.owned&&stopCount==1&&lastReason==1);}
 else {assert(safety.expired(testMs));stopControl(1);}
 accept(rc(1700,1800));assert(!safety.owned);
 accept(rc(1500,1500));assert(safety.owned==3);
 assert(vehicle.tx[vehicle.tx.size()-26+6]==0xdc); // reacquisition is neutral, not motion
 // True FC loss is independent of fresh host/radio commands.
 testMs+=2500;assert(!freshFc(testMs));stopControl(2);assert(!safety.owned);
 accept(rc(1500,1500));assert(!safety.owned);
 fcAt=testMs;accept(rc(1500,1500));assert(safety.owned==3);
 // UART backpressure retains stop packets for retry; movement cannot slip through.
 vehicle.capacity=0;accept(rc(1600,1600));assert(stopPending&&!safety.owned);
 vehicle.capacity=1024;tryStop();assert(!stopPending);
 assert(mesh::u16(vehicle.tx.data()+vehicle.tx.size()-26+6)==0);

 resetHost();mesh::Packet p=makePacket(mesh::POLL,999);
 p.origin=p.sender=2;p.dest=1;p.boot=123;p.stops=7;p.reason=1;
 uint8_t wire[mesh::MAX];size_t n=mesh::seal(p,cfg.key,wire);assert(n);
 mesh::Packet decoded;assert(mesh::open(wire,n,cfg.key,decoded));
 assert(decoded.stops==7&&decoded.boot==123);
 wire[28]^=1;assert(!mesh::open(wire,n,cfg.key,decoded));wire[28]^=1;
 challenge.issue(999,testMs,90);assert(challenge.consume(999,testMs+89));assert(!challenge.consume(999,testMs+89));
 challenge.issue(999,testMs,90);assert(!challenge.consume(999,testMs+91));
 // Entire asynchronous SX1262 receive path (both compiled roles).
 if(TELERC_ROLE==BASE){
  radio.rx.assign(wire,wire+n);radioIRQ=true;pumpRadio();assert(rxCount>0);
  auto msg=usbMessages();assert(msg.back()=="TELERC_LORA_STATUS_V1,0,0,7,123,1,0");
  before=rxCount;radio.rx.assign(wire,wire+n);radioIRQ=true;pumpRadio();assert(rxCount==before);
 }else{
  p=makePacket(mesh::COMMAND,999);p.origin=p.sender=1;p.dest=2;
  auto neutral=rc(1500,1500);p.body[0]=26;memcpy(p.body+1,neutral.data(),26);p.n=27;
  n=mesh::seal(p,cfg.key,wire);challenge.issue(999,testMs,90);
  radio.rx.assign(wire,wire+n);radioIRQ=true;pumpRadio();assert(safety.owned==3);
 }
 resetHost();accept(rc(1500,1500));pins[0]=LOW;loop();
 testMs+=1001;fcAt=testMs;loop();assert(maintenance&&!radioOK&&!safety.owned);
 pins[0]=HIGH;loop();assert(maintenance&&!radioOK);
 // Stalled CDC cannot block the main loop or consume unbounded memory.
 resetHost();Serial.capacity=0;for(int i=0;i<30;++i)info();assert(usbCount==8);
 for(int i=0;i<1000;++i){serviceUsbTx();}
 assert(usbCount==8);
 Serial.capacity=3;drainUsb();assert(usbCount==0);
 // Expired telemetry cannot be replayed from a blocked USB output queue.
 resetHost();Serial.capacity=0;mesh::Packet old=makePacket(mesh::POLL,22);
 forwardStatus(old);assert(usbCount==1);testMs+=201;serviceUsbTx();
 assert(usbCount==0&&Serial.tx.empty());
 // CAD and TX deadline failure stops owned commands.
 resetHost();accept(rc(1500,1500));auto queued=makePacket(mesh::COMMAND,88);enqueue(queued,0);
 pumpTx();assert(scanning);testMs+=21;pumpRadio();assert(!radioOK&&!safety.owned);
 std::cout<<"SX1262 role "<<TELERC_ROLE<<": provisioning, 2000 rapid input cycles, neutral gate, ownership, timeout, FC loss, UART retry, authentication, replay, radio path, CDC stalls and CAD deadline passed\n";
}
