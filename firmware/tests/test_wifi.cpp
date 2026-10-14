#include <cassert>
#include <iostream>
#include "../TeleRCBridge/TeleRCBridge.ino"
int main(){
 WiFi.modeFailures=1;
 setup();
 assert(!apReady && wifiAttempts==1);
 assert(std::string(wifiState)=="mode-failed");
 clockMs=1999;loop();assert(wifiAttempts==1);
 WiFi.ipFailures=1;clockMs=2000;loop();assert(!apReady);
 assert(std::string(wifiState)=="ip-failed");
 WiFi.apFailures=1;clockMs=4000;loop();assert(!apReady);
 assert(std::string(wifiState)=="ap-start-failed");
 udp.beginFailures=1;clockMs=6000;loop();
 assert(apReady && !udpReady && WiFi.lastHidden==0 && WiFi.lastChannel==1);
 const int apStarts=WiFi.apCalls;
 clockMs=8000;loop();assert(apReady && udpReady && WiFi.apCalls==apStarts);
 std::cout<<"PASS mode/IP/AP failures retry; UDP retry preserves visible channel-1 AP\n";
 WiFi.clients=0;
 for(clockMs=9000;clockMs<15000;clockMs+=1000)loop();
 assert(WiFi.apCalls==apStarts);
 WiFi.clients=1;
 for(clockMs=15000;clockMs<20000;clockMs+=1000)loop();
 assert(WiFi.apCalls==apStarts);
 std::cout<<"PASS healthy AP never restarted for zero clients or connected idle clients\n";
 ownedChannels=3;targetSystem=1;controlActive=true;neutralRequired=false;
 lastControlMs=clockMs;WiFi.active=WIFI_OFF;
 loop();assert(!controlActive && !ownedChannels && neutralRequired);
 assert(apReady && udpReady && WiFi.apCalls==apStarts+1);
 assert(fc.frames.size()==2); // owned neutral + release
 std::cout<<"PASS detected AP loss recovers network with control released and neutral required\n";
 assert(std::string(PERSONAL_AP_PASSWORD)=="telerc123");
 std::cout<<"PASS fixed password; no application Preferences storage needed\n";
}
