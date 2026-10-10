/* TeleRC Mesh 0.1.1 -- LilyGO T3-S3 SX1262 V1.2/V1.3.
 * Flash the same sketch to every board. Hold BOOT while resetting for setup.
 * Blank boards start in setup, with RF OFF. See README.md before wiring.
 */
#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <Preferences.h>
#include <esp_system.h>
#include "MeshCore.h"

constexpr uint8_t GATEWAY=1, RELAY=2, ROVER=3, RAW_FC=0, FRAMED_MOTOR=1;
struct Config {
 uint32_t magic=0x544d0001;uint16_t network=1,node=1,gateway=1,rover=2;
 uint32_t khz=0;int8_t power=2;uint8_t role=GATEWAY,hops=1,backend=RAW_FC;
 uint8_t key[32]={};char wifi[64]="telerc123",admin[32]="telerc";
};
Config cfg;
SX1262 radio=new Module(7,33,8,34);
HardwareSerial vehicle(1);
WiFiUDP udp;
WebServer web(80);
mesh::Seen seen;mesh::Challenge challenge;mesh::Safety safety;
telerc::CommandMailbox commands;telerc::UartParser framed;
mesh::MavParser mav;
bool maintenance=false,radioOK=false,transmitting=false,scanning=false,pollInFlight=false;
volatile bool radioIRQ=false;
uint64_t inflightToken=0;
uint32_t txAt=0,pollAt=0,fcAt=0,hostAt=0,logAt=0,resetAt=0,lastStopTry=0;
uint32_t scanAt=0;size_t scanSlot=0;
bool haveFc=false,reboot=false,stopPending=false;
IPAddress host;
String csrf;
uint32_t rxCount=0,txCount=0,rejectCount=0,duplicateCount=0,dropCount=0;
struct Slot {uint8_t data[telerc::RADIO_MAX]={};size_t n=0;uint32_t at=0;};
Slot telemetry[3];
struct TxSlot {mesh::Packet p;bool active=false;uint32_t at=0,due=0;};
TxSlot queue[8];
struct Neighbor {uint16_t id=0;uint32_t at=0;float rssi=0;};Neighbor neighbors[16];

void IRAM_ATTR onRadio(){radioIRQ=true;}
bool validConfig(const Config&v){
 uint8_t key=0;for(auto b:v.key)key|=b;
 bool band=(v.khz>=400250&&v.khz<=519750)||(v.khz>=830250&&v.khz<=944750);
 bool ids=v.network&&v.node&&v.gateway&&v.rover&&v.gateway!=v.rover;
 bool role=v.role>=GATEWAY&&v.role<=ROVER;
 bool mapping=(v.role==GATEWAY?v.node==v.gateway:v.role==ROVER?v.node==v.rover:v.node!=v.gateway&&v.node!=v.rover);
 return v.magic==0x544d0001&&band&&ids&&role&&mapping&&key&&v.power>=2&&v.power<=17&&v.hops>=1&&v.hops<=3&&v.backend<=1&&
  memchr(v.wifi,0,sizeof(v.wifi))&&strlen(v.wifi)>=8&&strlen(v.wifi)<=63&&memchr(v.admin,0,sizeof(v.admin))&&strlen(v.admin)>=6;
}
bool localIP(IPAddress ip){return ip[0]==192&&ip[1]==168&&ip[2]==4&&ip[3]>1&&ip[3]<255;}
bool freshFc(uint32_t now){return haveFc&&uint32_t(now-fcAt)<2500;}
void remember(uint16_t id,float rssi,uint32_t now){
 size_t slot=0;uint32_t oldest=0;
 for(size_t i=0;i<16;++i){if(neighbors[i].id==id){slot=i;break;}uint32_t age=neighbors[i].id?uint32_t(now-neighbors[i].at):UINT32_MAX;if(age>=oldest){oldest=age;slot=i;}}
 neighbors[slot]={id,now,rssi};
}
void clearQueue(){for(auto&s:queue)s.active=false;}
bool enqueue(const mesh::Packet&p,uint32_t jitter){
 uint32_t now=millis();
 for(auto&s:queue)if(!s.active||uint32_t(now-s.at)>mesh::QUEUE_MS){s.p=p;s.at=now;s.due=now+jitter;s.active=true;return true;}
 ++dropCount;return false;
}
mesh::Packet makePacket(uint8_t kind,uint64_t token){
 mesh::Packet p;p.kind=kind;p.network=cfg.network;p.origin=cfg.node;p.sender=cfg.node;
 p.dest=kind==mesh::POLL?cfg.gateway:cfg.rover;p.limit=p.hops=cfg.hops;p.token=token;return p;
}
bool uartWrite(const uint8_t*p,size_t n){
 if(!n)return true;
 if(vehicle.availableForWrite()<int(n)||vehicle.write(p,n)!=n){++dropCount;return false;}return true;
}
void makeRc(uint8_t*out,uint16_t value,uint8_t seq){
 memset(out,0,26);out[0]=0xfe;out[1]=18;out[2]=seq;out[3]=255;out[4]=190;out[5]=70;
 for(int i=0;i<8;++i)mesh::put16(out+6+2*i,i<2?value:65535);
 out[22]=1;out[23]=1;telerc::CommandMailbox::checksumRc(out);
}
// One bounded UART write: neutral then release only the two channels we own.
void tryStop(){
 if(!stopPending)return;
 uint8_t out[80],rc[26];size_t used=0;
 makeRc(rc,1500,0);if(cfg.backend==RAW_FC){memcpy(out,rc,26);used=26;}else used=telerc::encodeUart(rc,26,out);
 makeRc(rc,0,1);if(cfg.backend==RAW_FC){memcpy(out+used,rc,26);used+=26;}else used+=telerc::encodeUart(rc,26,out+used);
 if(uartWrite(out,used))stopPending=false;
 lastStopTry=millis();
}
void stopControl(){
 if(safety.owned)stopPending=true;
 safety.latch();challenge.active=false;commands.clear();clearQueue();tryStop();
}
bool restartRx(){
 radioIRQ=false;int state=radio.startReceive();
 if(state!=RADIOLIB_ERR_NONE){radioOK=false;stopControl();return false;}return true;
}
void radioFault(){radioOK=false;transmitting=scanning=false;radio.standby();stopControl();Serial.println("RF fault: control latched OFF; reset board.");}
void pumpTx(){
 if(!radioOK||transmitting||scanning)return;
 uint32_t now=millis();
 for(auto&s:queue){
  if(!s.active)continue;
  if(uint32_t(now-s.at)>mesh::QUEUE_MS){s.active=false;++dropCount;continue;}
  if(int32_t(now-s.due)<0)continue;
  radioIRQ=false;
  if(radio.startChannelScan()!=RADIOLIB_ERR_NONE){radioFault();return;}
  scanSlot=size_t(&s-queue);scanAt=now;scanning=true;return;
 }
}
void forwardTelemetry(const uint8_t*p,size_t n){
 if(!n||mesh::telemetryClass(p,n)<0)return;
 IPAddress dest=host==IPAddress()?IPAddress(192,168,4,255):host;
 if(udp.beginPacket(dest,14550)){udp.write(p,n);udp.endPacket();}
}
void acceptCommands(const uint8_t*p,size_t n){
 uint32_t now=millis();
 if(!telerc::validBundle(p,n)){++rejectCount;return;}
 // Validate the complete bundle and safety transition before any UART write.
 mesh::Safety next=safety;telerc::CommandMailbox check;bool requestedStop=false;
 uint8_t out[3*(telerc::UART_MAX+6)];size_t used=0;
 for(size_t i=0;i<n;){size_t k=p[i++];const uint8_t*f=p+i;i+=k;
  if(!check.accept(f,k,now)){++rejectCount;return;}
  if(telerc::textEquals(f,k,"TELERC_DISCOVER_V1"))continue;
  if(telerc::textEquals(f,k,"TELERC_DISCONNECT_V1")){stopControl();return;}
  if(telerc::mavV1(f,k,70,18,124)){
   if(mesh::u16(f+6)==0||mesh::u16(f+8)==0){requestedStop=true;next.latch();continue;}
   if(stopPending||!next.rc(f,k,now)){++rejectCount;return;}
  }
  if(telerc::mavV1(f,k,76,33,152)&&f[8]==0x80&&f[9]==0x3f&&!next.centered(now)){++rejectCount;return;}
  if(cfg.backend==RAW_FC&&!freshFc(now)){++rejectCount;return;}
  if(cfg.backend==RAW_FC){memcpy(out+used,f,k);used+=k;}else used+=telerc::encodeUart(f,k,out+used);
 }
 if(requestedStop)stopControl();
 if(uartWrite(out,used)){safety=next;}else stopControl();
}
void pumpRadio(){
 if(!radioOK)return;
 uint32_t now=millis();
 if(scanning){
  if(radioIRQ){
   radioIRQ=false;scanning=false;int state=radio.getChannelScanResult();auto&s=queue[scanSlot];
   if(state==RADIOLIB_LORA_DETECTED){s.due=now+8+(esp_random()%18);restartRx();return;}
   if(state!=RADIOLIB_CHANNEL_FREE){radioFault();return;}
   if(!s.active||uint32_t(now-s.at)>mesh::QUEUE_MS){s.active=false;++dropCount;restartRx();return;}
   uint8_t out[mesh::MAX];size_t n=mesh::seal(s.p,cfg.key,out);auto p=s.p;s.active=false;
   if(!n){++rejectCount;restartRx();return;}
   // Do not occupy the direct channel with a response that cannot finish in
   // its challenge window. The rover independently rejects any late arrival.
   if(cfg.hops==1&&p.kind==mesh::COMMAND&&
      uint32_t(millis()-s.at)+(radio.getTimeOnAir(n)+999)/1000+2>mesh::timing(1).responseMs){
    ++dropCount;restartRx();return;
   }
   if(radio.startTransmit(out,n)!=RADIOLIB_ERR_NONE){radioFault();return;}
   transmitting=true;txAt=now;pollInFlight=p.kind==mesh::POLL&&p.origin==cfg.rover&&cfg.role==ROVER;inflightToken=p.token;++txCount;
  }else if(uint32_t(now-scanAt)>20)radioFault();
  return;
 }
 if(transmitting){
  if(radioIRQ){radioIRQ=false;radio.finishTransmit();transmitting=false;
   if(pollInFlight){challenge.issue(inflightToken,millis(),mesh::timing(cfg.hops).responseMs);pollAt=millis();}pollInFlight=false;restartRx();
  }else if(uint32_t(now-txAt)>100)radioFault();
  return;
 }
 if(!radioIRQ)return;
 radioIRQ=false;uint8_t in[mesh::MAX];size_t n=radio.getPacketLength();
 if(n<mesh::HEADER+mesh::TAG||n>sizeof(in)){radio.standby();restartRx();++rejectCount;return;}
 int state=radio.readData(in,n);float rssi=radio.getRSSI();if(!restartRx())return;
 mesh::Packet p;
 if(state!=RADIOLIB_ERR_NONE||!mesh::open(in,n,cfg.key,p)||p.network!=cfg.network||p.limit!=cfg.hops||p.sender==cfg.node||
    (p.kind==mesh::POLL?(p.origin!=cfg.rover||p.dest!=cfg.gateway):(p.origin!=cfg.gateway||p.dest!=cfg.rover))){++rejectCount;return;}
 if(!seen.admit(p,now)){++duplicateCount;return;}++rxCount;remember(p.sender,rssi,now);
 if(cfg.role==RELAY){if(p.hops>1){--p.hops;p.sender=cfg.node;enqueue(p,3+(esp_random()%10));}return;}
 if(p.dest!=cfg.node)return;
 if(cfg.role==GATEWAY&&p.kind==mesh::POLL){
  forwardTelemetry(p.body,p.n);
  mesh::Packet response=makePacket(mesh::COMMAND,p.token);response.n=commands.take(response.body,millis());enqueue(response,3);
 }else if(cfg.role==ROVER&&p.kind==mesh::COMMAND){
  if(!challenge.consume(p.token,now)){++rejectCount;return;}acceptCommands(p.body,p.n);
 }
}
void pumpUdp(){
 uint32_t now=millis();
 if(host!=IPAddress()&&uint32_t(now-hostAt)>5000){host=IPAddress();commands.clear();}
 for(int i=0;i<4;++i){int count=udp.parsePacket();if(count<=0)break;
  uint8_t in[telerc::UART_MAX];int n=udp.read(in,sizeof(in));while(udp.available())udp.read();
  IPAddress ip=udp.remoteIP();
  if(n!=count||!localIP(ip)||udp.remotePort()!=14550||(host!=IPAddress()&&host!=ip)){++rejectCount;continue;}
  if(commands.accept(in,size_t(n),now)){host=ip;hostAt=now;}else ++rejectCount;
 }
}
void takeVehicleFrame(const uint8_t*p,size_t n){
 int slot=mesh::telemetryClass(p,n);if(slot<0||n>telerc::RADIO_MAX)return;
 if(slot==1&&cfg.backend==RAW_FC&&p[(p[0]==0xfe?6:10)+5]!=3)return;
 memcpy(telemetry[slot].data,p,n);telemetry[slot].n=n;telemetry[slot].at=millis();
 if(slot==1){fcAt=millis();haveFc=true;}
}
void pumpVehicle(){
 for(size_t i=0;i<512&&vehicle.available();++i){uint8_t b=uint8_t(vehicle.read());
  if(cfg.backend==RAW_FC){if(mav.feed(b,millis()))takeVehicleFrame(mav.data,mav.total);}
  else if(framed.feed(b,millis()))takeVehicleFrame(framed.data+4,framed.length());
 }
}
void sendPoll(){
 uint32_t now=millis();if(transmitting||scanning||challenge.pending(now)||uint32_t(now-pollAt)<mesh::timing(cfg.hops).pollMs)return;
 for(auto&s:queue)if(s.active)return;
 uint64_t token=0;while(!token)token=(uint64_t(esp_random())<<32)|esp_random();
 mesh::Packet p=makePacket(mesh::POLL,token);
 for(auto&s:telemetry)if(s.n){size_t n=s.n;s.n=0;if(uint32_t(now-s.at)>1200)continue;p.n=n;memcpy(p.body,s.data,n);break;}
 // Only one outstanding token, issued when TX is complete, never at enqueue.
 challenge.active=false;if(enqueue(p,0))pollAt=now;
}
String escapeHtml(const char*p){String s;for(;*p;++p){switch(*p){case '&':s+="&amp;";break;case '<':s+="&lt;";break;case '>':s+="&gt;";break;case '\"':s+="&quot;";break;default:s+=*p;}}return s;}
bool authenticated(){if(web.authenticate("admin",cfg.admin))return true;web.requestAuthentication();return false;}
String numberField(const char*name,uint32_t value){return String("<label>")+name+"<input type=number name="+name+" value="+String(value)+" required></label>";}
void page(){
 if(!authenticated())return;
 String s=F("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>TeleRC Mesh</title><style>body{font:16px system-ui;background:#eff2f6;color:#182534;max-width:480px;margin:24px auto;padding:16px}form{background:white;padding:22px;border-radius:18px}label{display:block;margin:12px 0}input,select,button{box-sizing:border-box;width:100%;padding:12px;border:1px solid #bac3cf;border-radius:10px;color:#182534;background:#fff}button{background:#2459b8;color:white}small{display:block;line-height:1.5}</style><h2>TeleRC Mesh</h2><p>Setup mode — radio is OFF.</p><form method=post action=/save>");
 s+="<input type=hidden name=csrf value='"+csrf+"'>";
 s+="<label>Role<select name=role>";
 const char*roles[]={"Gateway (PC / Wi-Fi)","Relay node","Rover (UART)"};
 for(int i=1;i<=3;++i)s+="<option value="+String(i)+(cfg.role==i?" selected>":">")+roles[i-1]+"</option>";
 s+="</select></label>";
 s+=numberField("node",cfg.node)+numberField("network",cfg.network)+numberField("gateway",cfg.gateway)+numberField("rover",cfg.rover);
 s+="<label>Maximum radio legs<select name=hops>";
 for(int i=1;i<=3;++i)s+="<option value="+String(i)+(cfg.hops==i?" selected>":">")+String(i)+"</option>";
 s+="</select></label>";
 s+=numberField("frequency_khz",cfg.khz)+numberField("power_dbm",uint32_t(cfg.power));
 s+="<small>Use 1 radio leg for a fast direct pair; 2 or 3 legs for relays. All boards must match. Enter the permitted frequency. Fixed SF7 / BW500 / CR4:5.</small>";
 s+="<label>Rover UART<select name=backend><option value=0"+String(cfg.backend==RAW_FC?" selected>":">")+"ArduRover raw MAVLink</option><option value=1"+String(cfg.backend==FRAMED_MOTOR?" selected>":">")+"TeleRC motor framed UART</option></select></label>";
 s+="<label>Mesh key (64 hexadecimal characters)<input type=password name=key maxlength=64 autocomplete=off placeholder='Blank keeps existing key'></label>";
 s+="<label>Wi-Fi password (8–63 characters)<input type=password name=wifi maxlength=63 autocomplete=new-password placeholder='Blank keeps existing password'></label>";
 s+="<label>Setup password (6–31 characters)<input type=password name=admin maxlength=31 autocomplete=new-password placeholder='Blank keeps existing password'></label>";
 s+="<button>Save and restart</button></form><p>Initial Wi-Fi: telerc123 · setup: admin / telerc</p>";
 web.sendHeader("Cache-Control","no-store");web.send(200,"text/html",s);
}
bool parseNumber(const char*name,uint32_t min,uint32_t max,uint32_t&out){
 String s=web.arg(name);if(!s.length()||s.length()>9)return false;uint32_t v=0;
 for(size_t i=0;i<s.length();++i){if(s[i]<'0'||s[i]>'9')return false;v=v*10+uint32_t(s[i]-'0');}if(v<min||v>max)return false;out=v;return true;
}
void save(){
 if(!authenticated())return;
 if(web.arg("csrf")!=csrf){web.send(403,"text/plain","Invalid setup token");return;}
 Config next=cfg;uint32_t v=0;bool ok=true;
 auto field=[&](const char*n,uint32_t a,uint32_t b){bool r=parseNumber(n,a,b,v);ok&=r;return v;};
 next.role=field("role",1,3);next.node=field("node",1,65535);next.network=field("network",1,65535);
 next.gateway=field("gateway",1,65535);next.rover=field("rover",1,65535);next.hops=field("hops",1,3);
 next.khz=field("frequency_khz",400250,944750);next.power=field("power_dbm",2,17);next.backend=field("backend",0,1);
 String key=web.arg("key");if(key.length()){
  if(key.length()!=64)ok=false;else for(int i=0;i<32;++i){char pair[3]={key[2*i],key[2*i+1],0};char*end=nullptr;
   if(!isxdigit(pair[0])||!isxdigit(pair[1])){ok=false;break;}next.key[i]=uint8_t(strtoul(pair,&end,16));}
 }
 String wifi=web.arg("wifi"),admin=web.arg("admin");
 if(wifi.length()){if(wifi.length()<8||wifi.length()>63)ok=false;else wifi.toCharArray(next.wifi,sizeof(next.wifi));}
 if(admin.length()){if(admin.length()<6||admin.length()>31)ok=false;else admin.toCharArray(next.admin,sizeof(next.admin));}
 if(!ok||!validConfig(next)){web.send(400,"text/plain","Invalid profile. Check frequency, unique node IDs, role, passwords and nonzero key.");return;}
 Preferences pref;if(!pref.begin("telerc-mesh",false)){web.send(500,"text/plain","Storage failed");return;}
 bool stored=pref.putBytes("config",&next,sizeof(next))==sizeof(next);pref.end();
 if(!stored){web.send(500,"text/plain","Storage failed");return;}
 web.send(200,"text/plain","Saved. Release BOOT. Restarting in 1 second.");reboot=true;resetAt=millis();
}
void setup(){
 Serial.begin(115200);pinMode(0,INPUT_PULLUP);delay(30);
 Preferences pref;if(pref.begin("telerc-mesh",true)){
  Config stored;if(pref.getBytesLength("config")==sizeof(stored)&&pref.getBytes("config",&stored,sizeof(stored))==sizeof(stored)&&validConfig(stored))cfg=stored;pref.end();
 }
 maintenance=!validConfig(cfg)||digitalRead(0)==LOW;
 csrf=String(esp_random(),HEX)+String(esp_random(),HEX);
 if(maintenance||cfg.role==GATEWAY){
  WiFi.persistent(false);WiFi.mode(WIFI_AP);WiFi.setSleep(false);
  String ssid=String("TeleRC-")+(maintenance?"Setup-":"Mesh-")+String(cfg.node);
  if(!WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0))||!WiFi.softAP(ssid.c_str(),cfg.wifi,1,false,2)){
   Serial.println("Wi-Fi startup failed; RF OFF.");maintenance=true;return;
  }
  if(maintenance){web.on("/",HTTP_GET,page);web.on("/save",HTTP_POST,save);web.begin();Serial.printf("Setup %s at http://192.168.4.1; RF OFF.\n",ssid.c_str());return;}
  if(!udp.begin(14550)){Serial.println("UDP startup failed; RF OFF.");return;}
 }
 if(cfg.role==ROVER){vehicle.setRxBufferSize(1024);vehicle.setTxBufferSize(1024);vehicle.begin(115200,SERIAL_8N1,44,43);}
 SPI.begin(5,3,6,7);
 int state=radio.begin(cfg.khz/1000.0f,500.0,7,5,0x12,cfg.power,8,1.6);
 if(state!=RADIOLIB_ERR_NONE){Serial.printf("RF init failed %d; reset required.\n",state);return;}
 state=radio.setRxBoostedGainMode(true,true);
 if(state!=RADIOLIB_ERR_NONE){Serial.printf("RF RX gain setup failed %d; reset required.\n",state);return;}
 radio.setDio1Action(onRadio);radioOK=true;restartRx();
 Serial.printf("TeleRC Mesh 0.1.1 role=%u node=%u net=%u hops=%u UART=%u poll=%lu response=%lu ms; control OFF\n",cfg.role,cfg.node,cfg.network,cfg.hops,cfg.backend,(unsigned long)mesh::timing(cfg.hops).pollMs,(unsigned long)mesh::timing(cfg.hops).responseMs);
}
void loop(){
 uint32_t now=millis();
 if(maintenance){web.handleClient();if(reboot&&uint32_t(now-resetAt)>=1000)ESP.restart();delay(1);return;}
 if(cfg.role==ROVER){
  if(safety.expired(now)||(safety.owned&&cfg.backend==RAW_FC&&!freshFc(now)))stopControl();
  if(stopPending&&uint32_t(now-lastStopTry)>=100)tryStop();
  pumpVehicle();
 }
 if(cfg.role==GATEWAY)pumpUdp();
 pumpRadio();if(radioOK&&cfg.role==ROVER)sendPoll();pumpTx();
 if(uint32_t(now-logAt)>=2000){logAt=now;
  Serial.printf("RF=%u RX=%lu TX=%lu reject=%lu duplicate=%lu drop=%lu control=%u owned=%u\n",radioOK,(unsigned long)rxCount,(unsigned long)txCount,(unsigned long)rejectCount,(unsigned long)duplicateCount,(unsigned long)dropCount,safety.ready,safety.owned);
  for(const auto&v:neighbors)if(v.id&&uint32_t(now-v.at)<10000)Serial.printf(" heard node=%u RSSI=%.1f age=%lu ms\n",v.id,v.rssi,(unsigned long)(now-v.at));
 }
 delay(1);
}
