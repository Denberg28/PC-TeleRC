#pragma once
// LilyGO T3-S3 SX1262 Wi-Fi bridge 0.5.0. Used by the mutually exclusive runtime transport dispatcher.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_system.h>
#include "MeshCore.h"
#include "LinkLed.h"

constexpr int FC_RX_GPIO=44, FC_TX_GPIO=43, USER_LED_GPIO=37;
constexpr uint16_t UDP_PORT=14550;
constexpr uint32_t WIFI_RETRY_MS=2000, PEER_LOCK_MS=5000, WIFI_LED_MS=1500;
const char AP_SSID[]="TeleRC-Rover", AP_PASSWORD[]="telerc123";
static_assert(sizeof(AP_PASSWORD)>=9&&sizeof(AP_PASSWORD)<=64,"Use an 8-63 character Wi-Fi password");
const IPAddress AP_IP(192,168,4,1), AP_BROADCAST(192,168,4,255), NO_PEER(0,0,0,0);
HardwareSerial vehicle(1);
WiFiUDP udp;
mesh::Safety safety;
mesh::MavParser mav;
telerc::LinkLed linkLed;
IPAddress peer(0,0,0,0);
bool apReady=false,udpReady=false,haveFc=false;
uint32_t apAt=0,udpAt=0,apCheckAt=0,peerAt=0,fcAt=0,lastStopTry=0,diagAt=0;
uint32_t accepted=0,rejected=0,uartDrops=0,stopCount=0,wifiAttempts=0;
uint8_t stopMask=0,sequence=0;
const char* lastStop="startup";
int bootResetReason=0;
char diagnostic[256];size_t diagN=0,diagOffset=0;

bool freshFc(uint32_t now){return haveFc&&uint32_t(now-fcAt)<2500;}
bool uartWrite(const uint8_t*p,size_t n){
 if(!n)return true;
 if(vehicle.availableForWrite()<int(n)){++uartDrops;return false;}
 if(vehicle.write(p,n)!=n){++uartDrops;return false;}
 return true;
}
void makeStopFrame(uint8_t*out,uint16_t value){
 memset(out,0,26);out[0]=0xfe;out[1]=18;out[2]=sequence++;out[3]=255;out[4]=190;out[5]=70;
 for(int i=0;i<8;++i)mesh::put16(out+6+2*i,(i<2&&(stopMask&(1<<i)))?value:65535);
 out[22]=1;out[23]=1;telerc::CommandMailbox::checksumRc(out);
}
void tryStop(){
 if(!stopMask)return;
 uint8_t out[52];makeStopFrame(out,1500);makeStopFrame(out+26,0);
 if(uartWrite(out,sizeof(out)))stopMask=0;
 lastStopTry=millis();
}
void stopControl(const char*reason){
 if(safety.owned){stopMask|=safety.owned;++stopCount;lastStop=reason;}
 safety.latch();tryStop();
}
void forgetPeer(){peer=NO_PEER;linkLed.havePeer=false;}
void serviceLed(){
 static int previous=HIGH;
 const uint32_t now=millis();
 const int next=linkLed.on(now,apReady&&udpReady&&WiFi.softAPgetStationNum()>0&&freshFc(now),WIFI_LED_MS)?HIGH:LOW;
 if(previous!=next){digitalWrite(USER_LED_GPIO,next);previous=next;}
}
void serviceDiagnostic(){
 const uint32_t now=millis();
 if(uint32_t(now-diagAt)>=3000&&diagOffset==diagN){
  diagAt=now;
  int n=snprintf(diagnostic,sizeof(diagnostic),
   "ROLE=ROVER v0.5.0 MODE=WIFI AP=%u UDP=%u clients=%u FC=%u RX=%lu reject=%lu stops=%lu last=%s uartDrop=%lu up=%lu reset=%d\n",
   unsigned(apReady),unsigned(udpReady),unsigned(WiFi.softAPgetStationNum()),unsigned(freshFc(now)),
   static_cast<unsigned long>(accepted),static_cast<unsigned long>(rejected),static_cast<unsigned long>(stopCount),lastStop,
   static_cast<unsigned long>(uartDrops),static_cast<unsigned long>(now),bootResetReason);
  diagN=n>0&&n<int(sizeof(diagnostic))?size_t(n):0;diagOffset=0;
 }
 int room=Serial.availableForWrite();
 if(room>0&&diagOffset<diagN){
  size_t n=diagN-diagOffset;if(n>32)n=32;if(n>size_t(room))n=size_t(room);
  diagOffset+=Serial.write(reinterpret_cast<const uint8_t*>(diagnostic+diagOffset),n);
 }
}
void serviceWifi(){
 const uint32_t now=millis();
 if(apReady&&uint32_t(now-apCheckAt)>=1000){
  apCheckAt=now;
  if(!(WiFi.getMode()&WIFI_AP)||WiFi.softAPIP()!=AP_IP){
   stopControl("ap-lost");udp.stop();apReady=udpReady=false;forgetPeer();apAt=now-WIFI_RETRY_MS;
  }
 }
 // A lack of clients never restarts a healthy AP.
 if(!apReady&&uint32_t(now-apAt)>=WIFI_RETRY_MS){
  apAt=now;++wifiAttempts;
  WiFi.mode(WIFI_OFF);
  if(!WiFi.mode(WIFI_AP))return;
  if(!WiFi.softAPConfig(AP_IP,AP_IP,IPAddress(255,255,255,0))||
     !WiFi.softAP(AP_SSID,AP_PASSWORD,1,0,1)){WiFi.mode(WIFI_OFF);return;}
  apReady=true;apCheckAt=now;udpAt=now-WIFI_RETRY_MS;
 }
 if(apReady&&!udpReady&&uint32_t(now-udpAt)>=WIFI_RETRY_MS){udpAt=now;udpReady=udp.begin(UDP_PORT);}
}
void toPeer(const uint8_t*p,size_t n){
 if(!apReady||!udpReady)return;
 const IPAddress dest=(peer!=NO_PEER&&uint32_t(millis()-peerAt)<PEER_LOCK_MS)?peer:AP_BROADCAST;
 if(udp.beginPacket(dest,UDP_PORT)){udp.write(p,n);udp.endPacket();}
}
void pumpVehicle(){
 for(int i=0;i<512&&vehicle.available();++i){
  if(!mav.feed(uint8_t(vehicle.read()),millis()))continue;
  const int kind=mesh::telemetryClass(mav.data,mav.total);
  if(kind<0)continue;
  if(kind==1){fcAt=millis();haveFc=true;}
  toPeer(mav.data,mav.total);
 }
}
// UDP accepts complete PC TeleRC MAVLink1 frames, not CDC/LoRa framing.
// WPA2 protects AP access; CRC/source IDs are validation, not HMAC authentication.
bool acceptHost(uint8_t*p,size_t n){
 const uint32_t now=millis();
 telerc::CommandMailbox check;
 if(!check.accept(p,n,now))return false;
 if(telerc::textEquals(p,n,"TELERC_DISCOVER_V1"))return true;
 if(telerc::textEquals(p,n,"TELERC_DISCONNECT_V1")){stopControl("disconnect");return true;}
 if(telerc::mavV1(p,n,70,18,124)){
  // Wi-Fi and LoRa use CH1 steering / CH2 throttle; preserve RC6 takeover.
  for(int i=2;i<8;++i)if(mesh::u16(p+6+2*i)!=65535)return false;
  if(mesh::u16(p+6)==0||mesh::u16(p+8)==0){stopControl("release");return true;}
  mesh::Safety next=safety;
  if(stopMask||!freshFc(now)||!next.rc(p,n,now))return false;
  // Record ownership before write so a partial UART write also gets released.
  safety=next;
  if(!uartWrite(p,n)){stopControl("uart-failure");return false;}
  return true;
 }
 if(telerc::mavV1(p,n,76,33,152)){
  const bool arm=p[8]==0x80&&p[9]==0x3f;
  if(arm){if(stopMask||!freshFc(now)||!safety.centered(now))return false;}
  else stopControl("disarm");
 }
 if(!uartWrite(p,n)){stopControl("uart-failure");return false;}
 return true;
}
void pumpUdp(){
 if(!apReady||!udpReady||WiFi.softAPgetStationNum()==0)return;
 const int packetSize=udp.parsePacket();if(packetSize<=0)return;
 const IPAddress sender=udp.remoteIP();const uint16_t port=udp.remotePort();
 uint8_t p[telerc::UART_MAX];const int n=udp.read(p,sizeof(p));
 // Bounded to the remaining bytes of this one datagram; oversized frames reject.
 for(int i=n>0?n:0;i<packetSize&&udp.available();++i)udp.read();
 const uint32_t now=millis();
 const bool local=sender[0]==192&&sender[1]==168&&sender[2]==4&&sender[3]>1&&sender[3]<255;
 const bool allowed=peer==NO_PEER||peer==sender||(!safety.owned&&!stopMask&&uint32_t(now-peerAt)>=PEER_LOCK_MS);
 if(packetSize>int(sizeof(p))||n!=packetSize||port!=UDP_PORT||!local||!allowed){++rejected;return;}
 const bool disconnect=telerc::textEquals(p,n,"TELERC_DISCONNECT_V1");
 if(disconnect&&sender!=peer){++rejected;return;}
 if(!acceptHost(p,size_t(n))){++rejected;return;}
 ++accepted;
 if(disconnect){forgetPeer();return;}
 peer=sender;peerAt=now;linkLed.received(now);
}
void setup(){
 pinMode(USER_LED_GPIO,OUTPUT);digitalWrite(USER_LED_GPIO,HIGH);
 // Keep SX1262 deselected and held in reset; no LoRa control path is running.
 pinMode(7,OUTPUT);digitalWrite(7,HIGH);pinMode(8,OUTPUT);digitalWrite(8,LOW);
 bootResetReason=int(esp_reset_reason());Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT
 Serial.setTxTimeoutMs(1);
#endif
 vehicle.setRxBufferSize(4096);vehicle.setTxBufferSize(1024);
 vehicle.begin(115200,SERIAL_8N1,FC_RX_GPIO,FC_TX_GPIO);
 apAt=millis()-WIFI_RETRY_MS;serviceWifi();serviceLed();
}
void loop(){
 uint32_t now=millis();
 if(stopMask&&uint32_t(now-lastStopTry)>=100)tryStop();
 if(safety.expired(now))stopControl("command-timeout");
 else if(safety.owned&&!freshFc(now))stopControl("fc-timeout");
 if(apReady&&WiFi.softAPgetStationNum()==0){
  const bool hadPeer=peer!=NO_PEER;
  stopControl("wifi-client-lost");forgetPeer();
  // Discard queued packets from the old client session before accepting a new one.
  if(hadPeer){udp.stop();udpReady=false;udpAt=now-WIFI_RETRY_MS;}
 }
 serviceWifi();pumpVehicle();pumpUdp();serviceLed();serviceDiagnostic();delay(1);
}
