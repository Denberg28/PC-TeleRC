#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <cstring>
namespace telerc {
// SSD1306 128x64, SDA18/SCL17. Each loop sends one <=17-byte transaction.
// A missing/stuck OLED disables display output; it never gates motor control.
struct TinyOled {
 bool ready=false;uint8_t pixels[1024]={};size_t offset=1024;bool address=false;
 static const uint8_t*glyph(char c){
  static constexpr uint8_t letters[26][5]={
   {126,17,17,17,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,34,28},
   {127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},
   {0,65,127,65,0},{32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},
   {127,2,12,2,127},{127,4,8,16,127},{62,65,65,65,62},{127,9,9,9,6},
   {62,65,81,33,94},{127,9,25,41,70},{70,73,73,73,49},{1,1,127,1,1},
   {63,64,64,64,63},{31,32,64,32,31},{63,64,56,64,63},{99,20,8,20,99},
   {7,8,112,8,7},{97,81,73,69,67}};
  static constexpr uint8_t digits[10][5]={{62,81,73,69,62},{0,66,127,64,0},{66,97,81,73,70},{33,65,69,75,49},{24,20,18,127,16},{39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},{54,73,73,73,54},{6,73,73,41,30}};
  static constexpr uint8_t blank[5]={},arrow[5]={0,65,34,20,8},dash[5]={8,8,8,8,8},colon[5]={0,54,54,0,0},dot[5]={0,96,96,0,0},slash[5]={32,16,8,4,2};
  if(c>='a'&&c<='z')c-=32;
  if(c>='A'&&c<='Z')return letters[c-'A'];
  if(c>='0'&&c<='9')return digits[c-'0'];
  return c=='>'?arrow:c=='-'?dash:c==':'?colon:c=='.'?dot:c=='/'?slash:blank;
 }
 bool send(uint8_t kind,const uint8_t*p,size_t n){
  Wire.beginTransmission(0x3c);Wire.write(kind);Wire.write(p,n);
  if(Wire.endTransmission()!=0){ready=false;return false;}return true;
 }
 void begin(){
  Wire.begin(18,17);Wire.setClock(400000);Wire.setTimeOut(1);ready=true;
  const uint8_t commands[]={0xae,0xd5,0x80,0xa8,0x3f,0xd3,0,0x40,0x8d,0x14,0x20,2,0xa1,0xc8,0xda,0x12,0x81,0x7f,0xd9,0xf1,0xdb,0x40,0xa4,0xa6,0xaf};
  send(0,commands,sizeof(commands));
 }
 void rows(const char*const*lines){
  if(!ready)return;
  memset(pixels,0,sizeof(pixels));
  for(size_t row=0;row<8;++row)if(lines[row])for(size_t col=0;col<21&&lines[row][col];++col)
   memcpy(pixels+row*128+col*6,glyph(lines[row][col]),5);
  offset=0;address=true;
 }
 void step(){
  if(!ready||offset==sizeof(pixels))return;
  if(address){const uint8_t c[]={uint8_t(0xb0+offset/128),0,0x10};send(0,c,sizeof(c));address=false;return;}
  if(send(0x40,pixels+offset,16)){offset+=16;if(offset%128==0)address=true;}
 }
};
}
