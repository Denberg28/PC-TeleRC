#include <iostream>
#include <sstream>
#include <iomanip>
#include "Runtime.h"
int main(){
 setup();std::string line;
 while(std::getline(std::cin,line)){
  for(size_t i=0;i+1<line.size();i+=2)Serial.rx.push_back(static_cast<uint8_t>(std::stoul(line.substr(i,2),nullptr,16)));
  pumpUsb();for(auto byte:Serial.tx)std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(byte);
  std::cout<<std::endl;Serial.tx.clear();
 }
}
