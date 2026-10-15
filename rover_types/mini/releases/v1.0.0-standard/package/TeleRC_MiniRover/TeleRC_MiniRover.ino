#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_arduino_version.h>
#include <esp_system.h>
#include "Config.h"
#include "RoverCore.h"
#include "MiniMavlink.h"
#include "ReceiverPWM.h"
#include "MotorOutputs.h"

#if !defined(CONFIG_IDF_TARGET_ESP32S3) && !defined(TELERC_HOST_TEST)
#error "Select ESP32S3 Dev Module: this release targets ESP32-S3 hardware profiles."
#endif

const IPAddress AP_IP(192,168,4,1), ZERO_IP(0,0,0,0);
const char DISCOVERY[]="TELERC_DISCOVER_V1";
const char DISCONNECT[]="TELERC_DISCONNECT_V1";
WiFiUDP udp;
IPAddress peer=ZERO_IP;
uint16_t peerPort=0;
uint32_t lastPeer=0, lastHeartbeat=0, lastMotorTick=0, lastLog=0;
uint32_t accepted=0, rejected=0, failsafes=0;
uint8_t txSequence=0;
bool pwmReady=false, bootHeld=false, wifiReady=false;
bool radioHealthy=false;
radio::Gate radioGate;
radio::Frame radioFrame;
rover::State state;
rover::Motor motors[4];
motor_output::Bank motorBank;

void coastAll() {
  motorBank.stopAll();
  for(auto &motor:motors) motor.output=0;
}
void stopRover(bool disarm) { state.stop(disarm); coastAll(); }
bool pcAuthority() {
  return radioHealthy && radioGate.selected==radio::Source::PC && radioGate.permit && !bootHeld;
}
void serviceRadio(uint32_t now) {
  radioFrame=receiver::snapshot();
  const radio::Source oldSource=radioGate.selected;
  const bool oldPermit=radioGate.permit;
  if(bootHeld) radioGate.reset();
  else radioGate.update(radioFrame,now);
  if(radioHealthy && !radioFrame.healthy) ++failsafes;
  radioHealthy=radioFrame.healthy;
  if(!radioHealthy || bootHeld || radioGate.selected==radio::Source::Stop ||
     oldSource!=radioGate.selected || (oldPermit && !radioGate.permit)) stopRover(true);
  if(radioGate.selected==radio::Source::Transmitter && radioGate.permit && !bootHeld) {
    state.rc(radioFrame.steer,radioFrame.drive,now);
    // Gate permission is granted only by neutral dwell plus a fresh OFF->ON
    // radio ARM edge. Transport failures never change that permission in TX.
    if(!oldPermit) { state.armed=true; state.inhibited=false; }
  }
}
bool localIP(const IPAddress &ip) {
  return ip[0]==192 && ip[1]==168 && ip[2]==4 && ip[3]>1 && ip[3]<255;
}
bool isPeer(const IPAddress &ip,uint16_t port) { return peer==ip && peerPort==port; }
void sendMessage(uint8_t id,const uint8_t *payload,uint8_t len,uint8_t extra) {
  if(!wifiReady || peer==ZERO_IP) return;
  uint8_t frame[48];
  const size_t n=mini_mav::encode(frame,txSequence++,config::SYSTEM_ID,
                         config::COMPONENT_ID,id,payload,len,extra);
  if(udp.beginPacket(peer,peerPort)) { udp.write(frame,n); udp.endPacket(); }
}
void heartbeat() {
  uint8_t payload[9]={};
  payload[4]=10; // MAV_TYPE_GROUND_ROVER
  payload[5]=0;  // MAV_AUTOPILOT_GENERIC: a real custom controller, not ArduPilot.
  payload[6]=64 | (state.armed ? 128 : 0); // manual input, armed bit
  payload[7]=state.armed ? 4 : 3; payload[8]=3;
  sendMessage(0,payload,9,50); lastHeartbeat=millis();
}
void commandAck(uint16_t command,uint8_t result) {
  uint8_t payload[3]; mini_mav::put16(payload,command); payload[2]=result;
  sendMessage(77,payload,3,143);
}
bool targetOK(uint8_t system,uint8_t component) {
  return system==config::SYSTEM_ID && (component==0 || component==config::COMPONENT_ID);
}
bool overrideOK(const mini_mav::Message &m) {
  if(!targetOK(m.payload[16],m.payload[17])) return false;
  const uint16_t s=mini_mav::u16(m.payload), d=mini_mav::u16(m.payload+2);
  const auto valid=[](uint16_t v) { return v==0 || (v>=1000 && v<=2000); };
  if(!valid(s) || !valid(d)) return false;
  // No auxiliary outputs. Ignore CH3..18; they never control motors or arm.
  return true;
}
bool dispatch(const mini_mav::Message &m,uint32_t now) {
  if(m.system!=config::GCS_SYSTEM_ID || m.component!=config::GCS_COMPONENT_ID) return false;
  if(m.id==0) return m.payload[4]==6 && m.payload[8]==3;
  if(m.id==70) {
    if(!overrideOK(m)) return false;
    if(!pcAuthority()) return false;
    const bool ok=state.rc(mini_mav::u16(m.payload),mini_mav::u16(m.payload+2),now);
    if(state.inhibited || !state.armed) coastAll();
    return ok;
  }
  if(m.id==76) {
    if(!targetOK(m.payload[30],m.payload[31])) return false;
    const uint16_t command=mini_mav::u16(m.payload+28);
    if(command!=400) { commandAck(command,3); return true; } // unsupported
    // In TX mode, PC monitoring/disconnect/commands cannot disarm or replace TX.
    if(!pcAuthority()) { commandAck(command,2); return true; }
    float param1; memcpy(&param1,m.payload,sizeof(param1));
    bool plain=true;
    for(int i=4;i<28;++i) if(m.payload[i]!=0) plain=false; // rejects force-arm
    if(!plain || !isfinite(param1) || (param1!=0.0f && param1!=1.0f)) {
      commandAck(command,2); return true;
    }
    if(param1==0) { stopRover(true); commandAck(command,0); }
    else if(!bootHeld && state.arm(now)) commandAck(command,0);
    else commandAck(command,2); // denied: send fresh centered CH1/CH2 first
    heartbeat(); return true;
  }
  return false;
}
void watchdog(uint32_t now) {
  const bool pressed=digitalRead(config::BOOT_STOP_PIN)==LOW;
  if(pressed) { radioGate.reset(); stopRover(true); }
  bootHeld=pressed;
  if(radioGate.selected==radio::Source::PC && state.haveRC &&
     rover::age(now,state.lastRC)>=config::CONTROL_TIMEOUT_MS) {
    stopRover(true); ++failsafes;
  }
  // Discovery and GCS heartbeat do not refresh the control watchdog.
  if(peer!=ZERO_IP && (rover::age(now,lastPeer)>=config::PEER_TIMEOUT_MS ||
                       WiFi.softAPgetStationNum()==0)) {
    if(radioGate.selected==radio::Source::PC) stopRover(true);
    peer=ZERO_IP; peerPort=0; ++failsafes;
  }
}
void receiveOne() {
  if(!wifiReady) return;
  const int size=udp.parsePacket(); if(size<=0) return;
  const IPAddress source=udp.remoteIP(); const uint16_t port=udp.remotePort();
  uint8_t data[256]; const int count=udp.read(data,sizeof(data));
  while(udp.available()) udp.read();
  if(size!=count || !localIP(source) || port!=config::UDP_PORT) { ++rejected; return; }
  const uint32_t now=millis();
  // Only exact discovery can acquire a lease. No drive command can steal it.
  if(size==int(sizeof(DISCOVERY)-1) && !memcmp(data,DISCOVERY,sizeof(DISCOVERY)-1)) {
    if(peer!=ZERO_IP && !isPeer(source,port)) { ++rejected; return; }
    if(peer==ZERO_IP) {
      if(radioGate.selected==radio::Source::PC) stopRover(true);
      peer=source; peerPort=port;
    }
    lastPeer=now; heartbeat(); ++accepted; return;
  }
  if(!isPeer(source,port)) { ++rejected; return; }
  if(size==int(sizeof(DISCONNECT)-1) && !memcmp(data,DISCONNECT,sizeof(DISCONNECT)-1)) {
    if(radioGate.selected==radio::Source::PC) stopRover(true);
    heartbeat(); peer=ZERO_IP; peerPort=0; ++accepted; return;
  }
  // Validate the complete datagram before any command side effects.
  size_t offset=0, used=0; mini_mav::Message m;
  while(offset<size_t(count)) {
    if(!mini_mav::decode(data+offset,count-offset,m,used) ||
        m.system!=config::GCS_SYSTEM_ID || m.component!=config::GCS_COMPONENT_ID ||
        (m.id==70 && !overrideOK(m))) { ++rejected; return; }
    offset+=used;
  }
  offset=0;
  while(offset<size_t(count)) {
    mini_mav::decode(data+offset,count-offset,m,used);
    if(dispatch(m,now)) { lastPeer=now; ++accepted; } else ++rejected;
    offset+=used;
  }
}
void updateMotors(uint32_t now) {
  if(rover::age(now,lastMotorTick)<config::MOTOR_TICK_MS) return;
  lastMotorTick=now;
  if(!state.armed || state.inhibited || !state.haveRC || bootHeld) { coastAll(); return; }
  int16_t left=0,right=0; state.mix(left,right);
  int16_t demands[4]={};
  for(uint8_t i=0;i<4;++i) {
    if(!hardware::active(i)) { motors[i].output=0; continue; }
    const int16_t target=motor_output::limitedDemand(i,i<2 ? left : right);
    demands[i]=motors[i].update(target,now);
  }
  motorBank.apply(demands,now);
}
void setup() {
  // Validate pin allocation before touching any configured output.
  if(!motorBank.prepare()) {
    Serial.begin(115200); Serial.println("FATAL invalid hardware pin profile; no outputs initialized");
    while(true) delay(1000);
  }
  pinMode(config::BOOT_STOP_PIN,INPUT_PULLUP);
  receiver::begin();
  if(config::STATUS_LED_PIN>=0) { pinMode(config::STATUS_LED_PIN,OUTPUT); digitalWrite(config::STATUS_LED_PIN,LOW); }
  Serial.begin(115200); // Never wait for a USB serial host.
  Serial.printf("TeleRC MiniRover %s; reset reason=%d\n",config::VERSION,int(esp_reset_reason()));
  if(!motorBank.begin()) {
    Serial.println("FATAL PWM setup; driver outputs disabled");
    while(true) delay(1000);
  }
  pwmReady=true; coastAll();
  Serial.printf("profile=%s motors=%u PWM=%luHz declared supply=%lumV (not measured)\n",
    hardware::driverName(),hardware::MOTOR_COUNT,(unsigned long)hardware::PWM_HZ,
    (unsigned long)hardware::SUPPLY_MAX_MV);
  WiFi.persistent(false); WiFi.mode(WIFI_AP); WiFi.setSleep(false);
  wifiReady=WiFi.softAPConfig(AP_IP,AP_IP,IPAddress(255,255,255,0)) &&
    WiFi.softAP(config::WIFI_SSID,config::WIFI_PASSWORD,6,0,1) && udp.begin(config::UDP_PORT);
  if(!wifiReady) Serial.println("Wi-Fi unavailable; PC disabled, FS-iA6 TX control still available");
  Serial.printf("AP=%s IP=192.168.4.1 UDP=%u; CH1=steer CH2=drive\n",config::WIFI_SSID,config::UDP_PORT);
}
void loop() {
  watchdog(millis()); // Expire old drive BEFORE accepting any queued packet.
  serviceRadio(millis()); // Local selector/ARM/receiver loss takes priority.
  receiveOne();       // One bounded datagram per iteration.
  const uint32_t now=millis(); watchdog(now); updateMotors(now);
  if(peer!=ZERO_IP && rover::age(now,lastHeartbeat)>=1000) heartbeat();
  if(config::STATUS_LED_PIN>=0) {
    const bool led=state.armed ? !state.inhibited || ((now/100)%2) : ((now/500)%2);
    digitalWrite(config::STATUS_LED_PIN,led ? HIGH : LOW);
  }
  if(rover::age(now,lastLog)>=1000) {
    lastLog=now;
    Serial.printf("source=%s rx=%u permit=%u armed=%u inhibit=%u CH1=%u CH2=%u ARM=%u SELECT=%u LF=%d LR=%d RF=%d RR=%d ok=%lu bad=%lu fs=%lu\n",
      radio::name(radioGate.selected),radioHealthy,radioGate.permit,state.armed,state.inhibited,
      radioFrame.steer,radioFrame.drive,radioFrame.arm,radioFrame.selector,motors[0].output,motors[1].output,
      motors[2].output,motors[3].output,(unsigned long)accepted,(unsigned long)rejected,(unsigned long)failsafes);
  }
  delay(1);
}
