#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_arduino_version.h>
#include <esp_system.h>
#include "Config.h"
#include "RoverCore.h"
#include "MiniMavlink.h"

#if !defined(CONFIG_IDF_TARGET_ESP32S3) && !defined(TELERC_HOST_TEST)
#error "Select ESP32S3 Dev Module: this sketch uses all eight S3 LEDC channels."
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
bool pwmReady=false, bootHeld=false;
rover::State state;
rover::Motor motors[4];

void pwmWrite(uint8_t index,uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(config::MOTOR_PINS[index/2][index%2],duty);
#else
  ledcWrite(index,duty);
#endif
}
void coastAll() {
  for(uint8_t i=0;i<8;++i) {
    if(pwmReady) pwmWrite(i,0);
    else digitalWrite(config::MOTOR_PINS[i/2][i%2],LOW);
  }
  // Retain reversal timers across stops: a subsequent opposite command still
  // owes the coast interval. There is deliberately no active short brake.
  for(auto &motor:motors) motor.output=0;
}
void stopRover(bool disarm) { state.stop(disarm); coastAll(); }
bool localIP(const IPAddress &ip) {
  return ip[0]==192 && ip[1]==168 && ip[2]==4 && ip[3]>1 && ip[3]<255;
}
bool isPeer(const IPAddress &ip,uint16_t port) { return peer==ip && peerPort==port; }
void sendMessage(uint8_t id,const uint8_t *payload,uint8_t len,uint8_t extra) {
  if(peer==ZERO_IP) return;
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
    if(bootHeld) return false;
    const bool ok=state.rc(mini_mav::u16(m.payload),mini_mav::u16(m.payload+2),now);
    if(state.inhibited || !state.armed) coastAll();
    return ok;
  }
  if(m.id==76) {
    if(!targetOK(m.payload[30],m.payload[31])) return false;
    const uint16_t command=mini_mav::u16(m.payload+28);
    if(command!=400) { commandAck(command,3); return true; } // unsupported
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
  if(pressed) stopRover(true);
  bootHeld=pressed;
  if(state.haveRC && rover::age(now,state.lastRC)>=config::CONTROL_TIMEOUT_MS) {
    stopRover(true); ++failsafes;
  }
  // Discovery and GCS heartbeat do not refresh the control watchdog.
  if(peer!=ZERO_IP && (rover::age(now,lastPeer)>=config::PEER_TIMEOUT_MS ||
                       WiFi.softAPgetStationNum()==0)) {
    stopRover(true); peer=ZERO_IP; peerPort=0; ++failsafes;
  }
}
void receiveOne() {
  const int size=udp.parsePacket(); if(size<=0) return;
  const IPAddress source=udp.remoteIP(); const uint16_t port=udp.remotePort();
  uint8_t data[256]; const int count=udp.read(data,sizeof(data));
  while(udp.available()) udp.read();
  if(size!=count || !localIP(source) || port!=config::UDP_PORT) { ++rejected; return; }
  const uint32_t now=millis();
  // Only exact discovery can acquire a lease. No drive command can steal it.
  if(size==int(sizeof(DISCOVERY)-1) && !memcmp(data,DISCOVERY,sizeof(DISCOVERY)-1)) {
    if(peer!=ZERO_IP && !isPeer(source,port)) { ++rejected; return; }
    if(peer==ZERO_IP) { stopRover(true); peer=source; peerPort=port; }
    lastPeer=now; heartbeat(); ++accepted; return;
  }
  if(!isPeer(source,port)) { ++rejected; return; }
  if(size==int(sizeof(DISCONNECT)-1) && !memcmp(data,DISCONNECT,sizeof(DISCONNECT)-1)) {
    stopRover(true); heartbeat(); peer=ZERO_IP; peerPort=0; ++accepted; return;
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
  for(uint8_t i=0;i<4;++i) {
    int16_t target=i<2 ? left : right;
    if(config::MOTOR_INVERT[i]) target=-target;
    const int16_t output=motors[i].update(target,now);
    // Remove the opposite leg first; never command both inputs high.
    if(output>=0) { pwmWrite(i*2+1,0); pwmWrite(i*2,uint8_t(output)); }
    else { pwmWrite(i*2,0); pwmWrite(i*2+1,uint8_t(-output)); }
  }
}
void setup() {
  // Safe outputs before Serial, radio startup, or diagnostic work.
  for(uint8_t i=0;i<8;++i) {
    const uint8_t pin=config::MOTOR_PINS[i/2][i%2];
    pinMode(pin,OUTPUT); digitalWrite(pin,LOW);
  }
  pinMode(config::BOOT_STOP_PIN,INPUT_PULLUP);
  if(config::STATUS_LED_PIN>=0) { pinMode(config::STATUS_LED_PIN,OUTPUT); digitalWrite(config::STATUS_LED_PIN,LOW); }
  Serial.begin(115200); // Never wait for a USB serial host.
  Serial.printf("TeleRC MiniRover %s; reset reason=%d\n",config::VERSION,int(esp_reset_reason()));
  for(uint8_t i=0;i<8;++i) {
    const uint8_t pin=config::MOTOR_PINS[i/2][i%2];
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    if(!ledcAttachChannel(pin,config::PWM_HZ,8,i)) {
      Serial.println("FATAL PWM setup; outputs disabled");
      while(true) delay(1000);
    }
#else
    if(ledcSetup(i,config::PWM_HZ,8)==0) {
      Serial.println("FATAL PWM setup; outputs disabled");
      while(true) delay(1000);
    }
    ledcAttachPin(pin,i);
#endif
    // Explicitly zero each channel immediately, even during partial setup.
    pwmWrite(i,0);
  }
  pwmReady=true; coastAll();
  WiFi.persistent(false); WiFi.mode(WIFI_AP); WiFi.setSleep(false);
  if(!WiFi.softAPConfig(AP_IP,AP_IP,IPAddress(255,255,255,0)) ||
     !WiFi.softAP(config::WIFI_SSID,config::WIFI_PASSWORD,6,0,1) || !udp.begin(config::UDP_PORT)) {
    stopRover(true); Serial.println("FATAL Wi-Fi startup; motors disabled");
    while(true) delay(1000);
  }
  Serial.printf("AP=%s IP=192.168.4.1 UDP=%u; CH1=steer CH2=drive\n",config::WIFI_SSID,config::UDP_PORT);
}
void loop() {
  watchdog(millis()); // Expire old drive BEFORE accepting any queued packet.
  receiveOne();       // One bounded datagram per iteration.
  const uint32_t now=millis(); watchdog(now); updateMotors(now);
  if(peer!=ZERO_IP && rover::age(now,lastHeartbeat)>=1000) heartbeat();
  if(config::STATUS_LED_PIN>=0) {
    const bool led=state.armed ? !state.inhibited || ((now/100)%2) : ((now/500)%2);
    digitalWrite(config::STATUS_LED_PIN,led ? HIGH : LOW);
  }
  if(rover::age(now,lastLog)>=1000) {
    lastLog=now;
    Serial.printf("armed=%u inhibit=%u CH1=%u CH2=%u LF=%d LR=%d RF=%d RR=%d ok=%lu bad=%lu fs=%lu\n",
      state.armed,state.inhibited,state.steer,state.drive,motors[0].output,motors[1].output,
      motors[2].output,motors[3].output,(unsigned long)accepted,(unsigned long)rejected,(unsigned long)failsafes);
  }
  delay(1);
}
