#include <cassert>
#include <iostream>
#include "../TeleRC_4x_BTS7960_PWM_GlitchFilter/TeleRC_4x_BTS7960_PWM_GlitchFilter.ino"

void edge(unsigned ch,uint32_t at,int high){
 clockUs=at;levels[RC_IN_PIN[ch]]=high;captureEdge(ch);
}
void clean(unsigned ch,uint16_t width,uint32_t end){
 edge(ch,end-width,1);edge(ch,end,0);
}
void settle(uint32_t end){clockUs=end+50;snapshotInputs();loop();}
int main(){
 setup();
 for(uint32_t end=20000;end<=340000;end+=20000){
  for(unsigned ch=0;ch<4;ch++)clean(ch,1500,end);
  settle(end);
 }
 assert(sourceEnabled);
 for(uint32_t end=360000;end<=760000;end+=20000){
  for(unsigned ch=0;ch<4;ch++){
   const auto start=end-1800;
   edge(ch,start,1);edge(ch,start+1000,0);
   edge(ch,start+1020,1);edge(ch,end,0);
  }
  settle(end);
  assert(sourceEnabled);
  for(unsigned ch=0;ch<4;ch++)assert(pulseWidthUs[ch]==1800);
 }
 std::cout<<"PASS 20 us low notch inside valid PWM cannot become a false reverse command\n";
 // 3000 rapid differential frames, with noise before/after the minimum width.
 for(uint32_t end=780000;end<=60760000;end+=20000){
  for(unsigned ch=0;ch<4;ch++){
   const uint16_t width=((end/20000+ch/2)%2)?1000:2000;
   const uint32_t start=end-width;
   edge(ch,start,1);edge(ch,start+500,0);edge(ch,start+520,1);
   edge(ch,end,0);
  }
  settle(end);
  assert(sourceEnabled && !signalStops && !loopStops);
  for(unsigned ch=0;ch<4;ch++){
   const uint16_t width=((end/20000+ch/2)%2)?1000:2000;
   assert(pulseWidthUs[ch]==width && lastValidPulseUs[ch]==end);
   assert(!(duties[RPWM_PIN[ch]] && duties[LPWM_PIN[ch]]));
  }
 }
 std::cout<<"PASS 3000 noisy differential frames retain correct commands without a neutral latch\n";
 // Pending candidate does not renew freshness until the low is confirmed.
 const auto original=lastValidPulseUs[0];
 const uint32_t end=60800000;
 clean(0,1800,end);clockUs=end+29;snapshotInputs();
 assert(lastValidPulseUs[0]==original);
 clockUs=end+30;snapshotInputs();assert(lastValidPulseUs[0]==end);
 // A real loss still hard-stops at the original falling-edge deadline.
 clockUs=end+RC_TIMEOUT_US;loop();
 assert(!sourceEnabled && signalStops==1);
 for(unsigned ch=0;ch<4;ch++)assert(!duties[RPWM_PIN[ch]]&&!duties[LPWM_PIN[ch]]);
 // A notch ending at neutral width must never qualify a held full pedal as neutral.
 for(uint32_t t=end+160000;t<=end+500000;t+=20000){
  for(unsigned ch=0;ch<4;ch++){
   edge(ch,t-2000,1);edge(ch,t-500,0);edge(ch,t-480,1);edge(ch,t,0);
  }
  settle(t);assert(!sourceEnabled);
 }
 for(uint32_t t=end+520000;t<=end+820000;t+=20000){
  for(unsigned ch=0;ch<4;ch++)clean(ch,1500,t);
  settle(t);
 }
 assert(sourceEnabled);
 std::cout<<"PASS real timeout and 300 ms neutral recovery remain; noise cannot fake neutral\n";
 // Mock USB mutex/write contention, using the configured real API wait limit.
 assert(Serial.txTimeoutMs==1);
 Serial.busy=true;
 for(uint32_t t=end+840000;t<=end+1840000;t+=20000){
  for(unsigned ch=0;ch<4;ch++)clean(ch,1800,t);
  settle(t);assert(sourceEnabled && !loopStops);
  assert(uint32_t(clockUs-(t+50))<=2000);
 }
 std::cout<<"PASS contended USB diagnostics stay bounded and cannot create a 150 ms loop stop\n";
}
