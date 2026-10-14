#include <cassert>
#include <array>
#include <iostream>
#include "TeleRCLoRa_ROVER.ino"
void crc(std::vector<uint8_t>&p,uint8_t extra){uint16_t c=0xffff;for(size_t i=1;i<p.size()-2;++i)c=telerc::mavCrcByte(c,p[i]);c=telerc::mavCrcByte(c,extra);p[p.size()-2]=uint8_t(c);p.back()=uint8_t(c>>8);}
std::vector<uint8_t> rc(uint16_t steer,uint16_t drive){std::vector<uint8_t>p(26,0xff);p[0]=0xfe;p[1]=18;p[2]=0;p[3]=255;p[4]=190;p[5]=70;mesh::put16(p.data()+6,steer);mesh::put16(p.data()+8,drive);p[22]=1;p[23]=1;crc(p,124);return p;}
std::vector<uint8_t> heartbeat(bool rover=true){std::vector<uint8_t>p(17,0);p[0]=0xfe;p[1]=9;p[3]=rover?1:255;p[4]=rover?1:190;p[10]=rover?10:6;p[11]=rover?3:8;p[14]=3;crc(p,50);return p;}
std::vector<uint8_t> arm(bool enable=true){std::vector<uint8_t>p(41,0);p[0]=0xfe;p[1]=33;p[3]=255;p[4]=190;p[5]=76;if(enable){p[8]=0x80;p[9]=0x3f;}p[34]=0x90;p[35]=1;p[36]=1;p[37]=1;crc(p,152);return p;}
void fcHeartbeat(){for(auto b:heartbeat())vehicle.input.push_back(b);pumpVehicle();}
void receive(std::vector<uint8_t>p){udp.incoming=p;loop();}
void text(const char*s){receive(std::vector<uint8_t>(s,s+strlen(s)));}
int main(){
 setup();assert(Serial.txTimeoutMs==1);assert(apReady&&udpReady&&vehicle.rxPin==44&&vehicle.txPin==43);
 assert(std::string(AP_SSID)=="TeleRC-Rover"&&std::string(AP_PASSWORD)=="telerc123");
 assert(pinLevels[8]==LOW&&pinLevels[7]==HIGH); // LoRa reset held; no RadioLib linked
 receive(rc(1700,1600));assert(vehicle.frames.empty()&&!safety.owned);
 auto bad=heartbeat();bad.back()^=1;for(auto b:bad)vehicle.input.push_back(b);pumpVehicle();assert(!haveFc);
 fcHeartbeat();assert(haveFc&&udp.sent.back()==heartbeat());
 receive(rc(1700,1600));assert(!safety.owned);
 receive(arm());assert(vehicle.frames.empty());
 receive(rc(1500,1500));assert(safety.owned==3&&safety.ready);
 receive(arm());assert(vehicle.frames.back()==arm());
 receive(rc(1700,1600));assert(safety.owned==3&&vehicle.frames.back()==rc(1700,1600));
 auto prior=vehicle.frames.size();receive(arm());assert(vehicle.frames.size()==prior); // moving ARM rejected
 auto corrupt=rc(1500,1500);corrupt.back()^=1;receive(corrupt);assert(vehicle.frames.size()==prior);
 auto rc6=rc(1500,1500);mesh::put16(rc6.data()+16,2000);crc(rc6,124);receive(rc6);assert(vehicle.frames.size()==prior);
 assert(linkLed.havePeer);clockMs=peerAt+500;Serial.room=0;loop();
 assert(!safety.owned&&!safety.ready&&vehicle.frames.size()==prior+1);
 assert(vehicle.frames.back().size()==52&&mesh::u16(vehicle.frames.back().data()+6)==1500&&mesh::u16(vehicle.frames.back().data()+32)==0&&mesh::u16(vehicle.frames.back().data()+10)==65535);
 receive(rc(1700,1600));assert(!safety.owned);fcHeartbeat();receive(rc(1500,1500));receive(rc(1700,1600));assert(safety.owned==3);
 prior=vehicle.frames.size();text("TELERC_DISCONNECT_V1");assert(peer==NO_PEER&&!linkLed.havePeer&&!safety.owned&&vehicle.frames.size()==prior+1);
 prior=vehicle.frames.size();text("TELERC_DISCONNECT_V1");assert(vehicle.frames.size()==prior); // no monitor-only override
 fcHeartbeat();receive(rc(1500,1500));vehicle.txRoom=0;clockMs+=500;loop();assert(stopMask==3&&!safety.owned);
 receive(rc(1500,1500));assert(!safety.owned);vehicle.txRoom=2048;clockMs+=100;loop();assert(stopMask==0);
 vehicle.shortWrite=true;fcHeartbeat();receive(rc(1500,1500));assert(!safety.owned&&stopMask==3);vehicle.shortWrite=false;clockMs+=100;loop();assert(!stopMask);
 fcHeartbeat();receive(rc(1500,1500));int apCalls=WiFi.apCalls;WiFi.clients=0;loop();assert(!safety.owned&&peer==NO_PEER&&WiFi.apCalls==apCalls);
 clockMs+=1500;loop();assert(WiFi.apCalls==apCalls);WiFi.clients=1;fcHeartbeat();receive(rc(1700,1600));assert(!safety.owned);
 receive(rc(1500,1500));WiFi.active=WIFI_OFF;clockMs+=1000;loop();assert(apReady&&udpReady&&!safety.owned);
 fcHeartbeat();receive(rc(1500,1500));
 for(int i=0;i<26;++i){clockMs+=100;receive(rc(1500,1500));}
 assert(!safety.owned&&std::string(lastStop)=="fc-timeout");
 std::cout<<"PASS Wi-Fi startup, pins/AP identity, FC CRC, startup neutral, ARM neutral, drive/RC6 validation, 500 ms timeout, blocked USB, release/disconnect, pending stops, UART short write, AP/client loss and FC timeout\n";
 return 0;
}
