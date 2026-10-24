#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <iomanip>
#include "Runtime.h"
std::vector<uint8_t> unhex(const std::string&s){std::vector<uint8_t>r;if(s=="-")return r;for(size_t i=0;i<s.size();i+=2)r.push_back(std::stoul(s.substr(i,2),nullptr,16));return r;}
void hex(const uint8_t*p,size_t n){if(!n){std::cout<<'-';return;}for(size_t i=0;i<n;++i)std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(p[i]);std::cout<<std::dec;}
int main(){setup();std::string line;while(std::getline(std::cin,line)){
 std::istringstream in(line);uint32_t now;std::string rf,usb,uart;in>>now>>rf>>usb>>uart;clockMs=now;
 for(auto b:unhex(uart))fc.rx.push_back(b);if(ROLE==2){pumpFc();manualWatchdog();}
 for(auto b:unhex(usb))Serial.rx.push_back(b);if(ROLE==1)pumpUsb();
 auto packet=unhex(rf);if(!packet.empty())onPacket(packet.data(),packet.size());

#if ROLE == 1
 if(running)pollFleet();
#endif
 if(pending.n&&int32_t(now-pending.due)>=0){
  if(uint32_t(now-pending.at)<=500){hex(pending.bytes,pending.n);if(ROLE==1&&pending.kind==mission::SYNC){waiting=true;baseQuery.at=now;}}
  else std::cout<<'-';pending.n=0;
 }else std::cout<<'-';
 std::cout<<' ';hex(Serial.tx.data(),Serial.tx.size());Serial.tx.clear();
 std::cout<<' ';hex(fc.tx.data(),fc.tx.size());fc.tx.clear();
 std::cout<<' '<<int(selected)<<' '<<gate.verifiedUpload<<' '<<gate.started<<' '<<rejectCount<<'\n'<<std::flush;
}}
