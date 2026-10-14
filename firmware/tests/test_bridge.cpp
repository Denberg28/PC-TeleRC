#include <cassert>
#include <iostream>
#include <array>
#include "../TeleRCBridge/TeleRCBridge.ino"
void seal(std::vector<uint8_t>& p,uint8_t extra=124){
 uint16_t crc=0xffff;
 for(size_t i=1;i<p.size()-2;i++)crc=crcByte(crc,p[i]);
 crc=crcByte(crc,extra);p[p.size()-2]=uint8_t(crc);p.back()=uint8_t(crc>>8);
}
std::vector<uint8_t> rc(std::array<uint16_t,4> channels){
 std::vector<uint8_t> p(26,0xff);p[0]=0xfe;p[1]=18;p[2]=0;p[3]=255;p[4]=190;p[5]=70;
 for(int i=0;i<4;i++){p[6+i*2]=uint8_t(channels[i]);p[7+i*2]=uint8_t(channels[i]>>8);}
 p[22]=1;p[23]=1;seal(p);return p;
}
void receive(std::vector<uint8_t> p){udp.incoming=p;loop();}
int main(){
 setup();
 assert(Serial.txTimeoutMs==1);
 assert(std::string(PERSONAL_AP_PASSWORD)=="telerc123");
 if(ELRS_MODE){
   assert(WiFi.active==WIFI_OFF);
   auto p=rc({1700,1600,65535,65535});
   udp.incoming=p;loop();assert(fc.frames.empty());
   for(auto b:p)elrs.input.push_back(b);
   loop();assert(fc.frames.size()==1 && fc.frames.back()==p);
   std::vector<uint8_t> signedFrame(280,0);signedFrame[0]=0xfd;signedFrame[1]=255;signedFrame[2]=1;
   for(auto b:signedFrame)fc.input.push_back(b);
   loop();assert(elrs.frames.size()==1 && elrs.frames.back()==signedFrame);
   consumeElrsByte(0xfe);consumeElrsByte(18);clockMs+=101;consumeElrsByte(0x42);
   assert(elrsSize==0);
   for(auto b:p)elrs.input.push_back(b);
   Serial.room=0;loop();assert(fc.frames.size()==2);
   assert(!ownedChannels && !controlActive);
   std::cout<<"PASS ELRS exclusivity, uplink, signed maximum telemetry, partial timeout, disconnected USB\n";
   return 0;
 }
 auto drive=rc({1700,1600,65535,65535});
 receive(drive);assert(fc.frames.empty() && neutralRequired);
 receive(rc({1500,1500,65535,65535}));assert(ownedChannels==3 && controlActive);
 receive(drive);assert(fc.frames.back()==drive);
 std::cout<<"PASS PC sparse CH1/CH2 and startup neutral gate\n";
 auto corrupt=drive;corrupt.back()^=1;size_t n=fc.frames.size();receive(corrupt);assert(fc.frames.size()==n);
 assert(!validTeleRcCommand(drive.data(),25));
 assert(!validTeleRcCommand(rc({0,1600,65535,65535}).data(),26));
 std::cout<<"PASS CRC, length, mixed release rejection\n";
 clockMs=lastControlMs+500;loop();assert(!controlActive && neutralRequired);
 assert(fc.frames.size()==n+2);
 auto neutral=fc.frames[n],release=fc.frames[n+1];
 assert(channelValue(neutral.data(),0)==1500 && channelValue(neutral.data(),2)==65535);
 assert(channelValue(release.data(),0)==0 && channelValue(release.data(),2)==65535);
 receive(drive);assert(!controlActive);
 assert(std::string(lastStopReason)=="command-timeout" && lastStopGapMs>=500);
 assert(neutralRejects==2);
 std::cout<<"PASS timeout stops only owned channels and rejects non-neutral recovery\n";
 receive(rc({1500,1500,65535,65535}));receive(drive);
 assert(std::string(lastStopReason)=="command-timeout");
 receive(rc({0,0,65535,65535}));assert(!ownedChannels);
 n=fc.frames.size();receive(rc({0,0,65535,65535}));assert(fc.frames.size()==n);
 std::cout<<"PASS sparse release and monitor-only duplicate release\n";
 receive(rc({1500,1500,1500,1500}));assert(ownedChannels==15);
 receive(rc({1600,1600,1600,1600}));assert(controlActive);
 receive(std::vector<uint8_t>(DISCONNECT,DISCONNECT+strlen(DISCONNECT)));
 assert(!controlActive && phone==IPAddress(0,0,0,0));
 std::cout<<"PASS original four-channel format and explicit disconnect\n";
 std::vector<uint8_t> hb(17,0);hb[0]=0xfe;hb[1]=9;hb[3]=255;hb[4]=190;hb[10]=6;hb[11]=8;hb[14]=3;seal(hb,50);
 assert(validPcAuxiliary(hb.data(),hb.size()));receive(hb);assert(fc.frames.back()==hb && !controlActive);
 std::vector<uint8_t> arm(41,0);arm[0]=0xfe;arm[1]=33;arm[3]=255;arm[4]=190;arm[5]=76;
 arm[8]=0x80;arm[9]=0x3f;arm[34]=0x90;arm[35]=1;arm[36]=1;arm[37]=1;seal(arm,152);
 receive(arm);assert(fc.frames.back()==arm && !controlActive);
 arm[10]=1;seal(arm,152);assert(!validPcAuxiliary(arm.data(),arm.size()));
 std::cout<<"PASS explicit normal ARM and heartbeat whitelist; force params rejected\n";
 receive(rc({1500,1500,65535,65535}));
 fc.shortWrite=true;receive(drive);assert(!controlActive && neutralRequired);fc.shortWrite=false;
 std::cout<<"PASS short UART write latches control off\n";
 Serial.room=0;receive(rc({1500,1500,65535,65535}));receive(drive);
 clockMs=lastControlMs+500;loop();assert(!controlActive);
 clockMs=0xffffff00U;receive(rc({1500,1500,65535,65535}));
 clockMs=uint32_t(lastControlMs+500);loop();assert(!controlActive);
 std::cout<<"PASS blocked USB does not suspend timeout; millis wrap handled\n";
}

