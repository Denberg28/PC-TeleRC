#pragma once
#include <Arduino.h>
#include <algorithm>
#include <cctype>
#include <SPI.h>
#include <RadioLib.h>
#include <Preferences.h>
#include <esp_system.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include "MeshCore.h"
#include "LinkLed.h"
#include "LinkMode.h"
#include "Pairing.h"
#include "BootMenu.h"
#include "TinyOled.h"
// Include driver APIs above the namespaces; only backend state is namespaced.
#define TELERC_RUNTIME_MENU 1
namespace lora {
#include "Link.h"
}
#if TELERC_ROLE == 3
namespace wifi {
#include "WiFiLink.h"
}
#endif

namespace runtime {
constexpr uint8_t WIFI_MODE=1,LORA_MODE=0;
// AppSettings allows at most 15 s heartbeat age. Setup holds telemetry OFF
// beyond that before restart, so an old PC session cannot silently stay enabled.
constexpr uint32_t RESTART_MIN_PAUSE_MS=16000;
telerc::BootButton button;telerc::TinyOled oled;WebServer server(80);
uint8_t mode=LORA_MODE,choice=0;bool menu=false,statusPage=false,portal=false,restarting=false;
uint32_t pausedAt=0,paintedAt=0,restartAt=0;char csrf[17]={};const char*notice="";

bool pendingStop(){
#if TELERC_ROLE == 3
 if(mode==WIFI_MODE)return wifi::stopMask!=0;
#endif
 return lora::stopPending;
}
bool saveMode(uint8_t selected){
 Preferences p;if(!p.begin("telerc-ui",false))return false;
 bool ok=p.putUChar("mode",selected)==1;p.end();return ok;
}
void loadConfig(){
 Preferences p;if(!p.begin("telerc-lora2",true))return;
 lora::Config c;if(p.getBytesLength("config")==sizeof(c)&&p.getBytes("config",&c,sizeof(c))==sizeof(c)&&lora::validConfig(c))lora::cfg=c;
 p.end();
}
void paint(){
 char title[24],line[24],count[40],freq[24];
 snprintf(title,sizeof(title),"TELERC %s",TELERC_ROLE==1?"BASE":"ROVER");
 snprintf(line,sizeof(line),"MODE: %s",mode==WIFI_MODE?"WI-FI":"LORA");
 snprintf(freq,sizeof(freq),"LORA %lu.%03lu MHZ",(unsigned long)(lora::cfg.khz/1000),(unsigned long)(lora::cfg.khz%1000));
 const char*rows[8]={title,line,"","","","","",""};
 if(restarting){
  uint32_t elapsed=millis()-pausedAt;uint32_t remaining=elapsed<RESTART_MIN_PAUSE_MS?(RESTART_MIN_PAUSE_MS-elapsed+999)/1000:0;
  snprintf(count,sizeof(count),"RESTART IN %lu S",(unsigned long)remaining);
  rows[2]="CONTROL STOPPED";rows[3]=count;rows[4]="REENABLE PC MANUALLY";
 }else if(portal){rows[2]="SETUP WIFI:";rows[3]=TELERC_ROLE==1?"TELERC-SETUP-BASE":"TELERC-SETUP-ROVER";rows[4]="PW: TELERC123";rows[5]="192.168.4.1";rows[6]="HOLD BOOT TO EXIT";
 }else if(menu&&!statusPage){
  const char*selected;
  if(TELERC_ROLE==3){const char*items[]={"> WI-FI","> LORA","> LINK SETTINGS","> STATUS","> EXIT / RESTART"};selected=items[choice];}
  else {const char*items[]={"> LORA","> LINK SETTINGS","> STATUS","> EXIT / RESTART"};selected=items[choice];}
  rows[2]="CONTROL STOPPED";rows[3]=selected;rows[4]="TAP: NEXT";rows[5]="HOLD: SELECT";rows[6]=pendingStop()?"STOP WRITE PENDING":notice;
 }else {
  rows[2]=freq;
  if(mode==WIFI_MODE){
#if TELERC_ROLE == 3
   snprintf(count,sizeof(count),"FC:%u CLIENTS:%u",unsigned(wifi::freshFc(millis())),unsigned(WiFi.softAPgetStationNum()));
   rows[3]=count;rows[4]=menu?"SETUP PAUSED":(wifi::safety.owned?"PC CONTROL ACTIVE":"PC CONTROL OFF");
#endif
  }else{snprintf(count,sizeof(count),"RX:%lu STOPS:%lu",(unsigned long)lora::rxCount,(unsigned long)lora::stopCount);rows[3]=count;rows[4]=menu?"SETUP PAUSED":(lora::radioOK&&!lora::maintenance?"RADIO READY":"PAIRING REQUIRED");}
  rows[5]=menu?"TAP: BACK":"HOLD BOOT: MENU";
 }
 oled.rows(rows);paintedAt=millis();
}
void pause(){
 menu=true;statusPage=false;pausedAt=millis();choice=0;notice="";
#if TELERC_ROLE == 3
 if(mode==WIFI_MODE){wifi::stopControl("setup");wifi::udp.stop();wifi::udpReady=false;}
 else
#endif
 {lora::stopControl(4);lora::radio.standby();lora::radioOK=false;lora::transmitting=lora::scanning=false;}
 lora::maintenance=true;lora::radioOK=false;paint();
}
bool restart(uint8_t selected){
 if(!menu||pendingStop()){notice="WAIT FOR STOP WRITE";paint();return false;}
 if(!saveMode(selected)){notice="STORAGE FAILED";paint();return false;}
 mode=selected;restarting=true;restartAt=millis();paint();return true;
}
String form(){
 char f[24];snprintf(f,sizeof(f),"%lu.%03lu",(unsigned long)(lora::cfg.khz/1000),(unsigned long)(lora::cfg.khz%1000));
 String html=String("<!doctype html><meta name='viewport' content='width=device-width'><title>TeleRC setup</title><style>body{font:16px system-ui;max-width:420px;margin:30px auto;padding:16px}input,select,button{box-sizing:border-box;width:100%;padding:12px;margin:6px 0 16px}small{color:#555}</style><h2>TeleRC link setup</h2><p>Control is stopped. Configure BASE and ROVER with the same frequency and password.</p><form method='post' action='/save'><input type='hidden' name='csrf' value='")+csrf+"'><label>Transport</label><select name='mode'>";
 if(TELERC_ROLE==3){html+="<option value='1'";if(mode==WIFI_MODE)html+=" selected";html+=">Wi-Fi rover</option>";}
 html+="<option value='0'";if(mode==LORA_MODE)html+=" selected";
 html+=">LoRa</option></select><label>LoRa frequency (MHz)</label><input name='mhz' inputmode='decimal' required maxlength='7' value='";
 if(lora::cfg.khz)html+=f;
 html+="'><label>Power (dBm)</label><input name='power' type='number' min='2' max='17' required value='"+String(unsigned(lora::cfg.power))+"'><label>LoRa link password: exactly 8 characters</label><input name='password' id='pw' type='password' minlength='8' maxlength='8' autocomplete='new-password' required><button type='button' onclick=\"let p=document.getElementById('pw');p.type=p.type==='password'?'text':'password'\">Show / hide</button><small>Password is never read back. Existing pairing is replaced only when you save. Use a frequency matching your hardware and permitted band.</small><button>Save and restart</button></form>";
 return html;
}
void startPortal(){
 if(pendingStop()){notice="WAIT FOR STOP WRITE";paint();return;}
 WiFi.mode(WIFI_OFF);
 if(!WiFi.mode(WIFI_AP)){notice="SETUP WIFI FAILED";paint();return;}
 if(!WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0))||
    !WiFi.softAP(TELERC_ROLE==1?"TeleRC-Setup-BASE":"TeleRC-Setup-ROVER","telerc123",1,0,1)){
  notice="SETUP WIFI FAILED";paint();return;
 }
 snprintf(csrf,sizeof(csrf),"%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random());
 server.on("/",HTTP_GET,[]{server.sendHeader("Cache-Control","no-store");server.send(200,"text/html",form());});
 server.on("/save",HTTP_POST,[]{
  server.sendHeader("Cache-Control","no-store");
  if(!menu||!portal||restarting||pendingStop()||server.arg("csrf")!=csrf){server.send(409,"text/plain","Setup unavailable. Use BOOT to enter setup.");return;}
  String pw=server.arg("password");lora::Config next=lora::cfg;uint32_t power=0;
  const String selected=server.arg("mode");
  bool valid=(selected=="0"||(TELERC_ROLE==3&&selected=="1"))&&telerc::frequencyKHz(server.arg("mhz").c_str(),next.khz)&&
    lora::parseNumber(server.arg("power").c_str(),2,17,power)&&telerc::passwordKey(pw.c_str(),pw.length(),next.key);
  for(size_t i=0;i<pw.length();++i)pw.setCharAt(i,0);
  next.power=uint8_t(power);
  if(!valid||!lora::validConfig(next)){server.send(400,"text/plain","Use a valid hardware frequency, power 2-17 and exactly eight visible ASCII password characters.");return;}
  Preferences p;if(!p.begin("telerc-lora2",false)){server.send(500,"text/plain","Storage failed.");return;}
  bool saved=p.putBytes("config",&next,sizeof(next))==sizeof(next);p.end();
  if(!saved){server.send(500,"text/plain","Storage failed.");return;}
  lora::cfg=next;
  if(!restart(selected=="1"?WIFI_MODE:LORA_MODE)){server.send(500,"text/plain","Mode save failed. LoRa pairing was saved; retry mode selection using BOOT.");return;}
  server.send(200,"text/plain","Saved. Restart waits for the previous control session to time out. Reconnect and manually enable at neutral. Set the partner board to the same frequency/password.");
 });
 server.begin();portal=true;paint();
}
void select(){
 if(TELERC_ROLE==3){if(choice<2){restart(choice==0?WIFI_MODE:LORA_MODE);return;}if(choice==2){startPortal();return;}if(choice==3){statusPage=true;paint();return;}}
 else {if(choice==0){restart(LORA_MODE);return;}if(choice==1){startPortal();return;}if(choice==2){statusPage=true;paint();return;}}
 restart(mode);
}
void setup(){
 pinMode(0,INPUT_PULLUP);loadConfig();
 mode=TELERC_ROLE==1?LORA_MODE:uint8_t(TELERC_TRANSPORT_WIFI);
 Preferences p;if(p.begin("telerc-ui",true)){uint8_t saved=p.getUChar("mode",mode);if(saved<=1)mode=saved;p.end();}
 if(TELERC_ROLE==1)mode=LORA_MODE;
 oled.begin();
#if TELERC_ROLE == 3
 if(mode==WIFI_MODE)wifi::setup();else
#endif
 lora::setup();
 paint();
}
void loop(){
 uint32_t now=millis();telerc::Press event=button.update(digitalRead(0)==LOW,now);
 if(!menu){
  if(event==telerc::Press::HOLD){pause();event=telerc::Press::NONE;}
  if(!menu){
#if TELERC_ROLE == 3
   if(mode==WIFI_MODE)wifi::loop();else
#endif
   lora::loop();
  }
 }
 if(menu){
  if(pendingStop()){
#if TELERC_ROLE == 3
   if(mode==WIFI_MODE){if(uint32_t(now-wifi::lastStopTry)>=100)wifi::tryStop();}else
#endif
   if(uint32_t(now-lora::lastStopTry)>=100)lora::tryStop();
  }
  // Local framing/provisioning only. Radio is OFF, so drive bundles reject.
  lora::pumpUsb();lora::serviceUsbTx();
  if(portal&&!restarting)server.handleClient();
  if(!restarting){
   if(event==telerc::Press::TAP){if(statusPage)statusPage=false;else if(!portal)choice=(choice+1)%(TELERC_ROLE==3?5:4);paint();}
   if(event==telerc::Press::HOLD){if(portal)restart(mode);else if(!statusPage)select();else{statusPage=false;paint();}}
  }
  if(restarting&&!pendingStop()&&uint32_t(now-pausedAt)>=RESTART_MIN_PAUSE_MS&&uint32_t(now-restartAt)>=1000){ESP.restart();return;}
  lora::serviceLed();delay(1);
 }
 if(uint32_t(now-paintedAt)>=1000)paint();
 oled.step();
}
}
