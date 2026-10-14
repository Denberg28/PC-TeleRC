#include <cassert>
#include <iostream>
#include "../TeleRC_4x_BTS7960_PWM_GlitchFilter/TeleRC_4x_BTS7960_PWM_GlitchFilter.ino"
void pulse(unsigned ch, uint16_t width, uint32_t end) {
  clockUs=end-width; levels[RC_IN_PIN[ch]]=1; captureEdge(ch);
  clockUs=end; levels[RC_IN_PIN[ch]]=0; captureEdge(ch);
}
void frame(uint32_t t, uint16_t left, uint16_t right) {
  for(unsigned i=0;i<4;i++) pulse(i, i<2 ? left : right, t);
  clockUs=t;loop();
}
int main() {
  setup();
  for(uint32_t t=20000;t<=340000;t+=20000)frame(t,1500,1500);
  assert(sourceEnabled);
  // Rapid differential commands plus isolated electrical-edge glitches.
  for(uint32_t t=345000;t<=10340000;t+=5000) {
    if(t%20000==0) {
      bool turn=(t/20000)%2;
      frame(t,turn?2000:1000,turn?1000:2000);
      pulse(1,100,t+100);
    }
    clockUs=t+100;loop();
    assert(sourceEnabled && !signalStops && !loopStops);
    assert(currentCmd[0]==currentCmd[1] && currentCmd[2]==currentCmd[3]);
    for(unsigned i=0;i<4;i++)assert(!(duties[RPWM_PIN[i]] && duties[LPWM_PIN[i]]));
  }
  std::cout<<"PASS 2000 rapid differential ticks and isolated bad edges keep control active\n";
  uint32_t end=lastValidPulseUs[1];
  // Only M6 loses signal. Continue servicing the loop and other three inputs.
  for(uint32_t t=end+5000;t<=end+150000;t+=5000) {
    if(t%20000==0) for(unsigned i=0;i<4;i++) if(i!=1)pulse(i,1500,t);
    clockUs=t;loop();
  }
  assert(!sourceEnabled && signalStops==1);
  assert(lastFaultMask==2 && lastFaultAgeUs[1]==150000);
  assert(std::string(lastFaultCause)=="input-timeout");
  uint32_t faultAt=lastFaultAtMs;
  for(uint32_t t=end+160000;t<=end+500000;t+=20000)frame(t,1500,1500);
  assert(sourceEnabled && lastFaultAtMs==faultAt && lastFaultMask==2);
  // Worst-case counters still fit and produce a complete nonblocking record.
  for(unsigned i=0;i<4;i++)snapshotRejected[i]=UINT32_MAX;
  diagnosticOffset=diagnosticLength;lastDiagMs=0;serviceDiagnostics(clockUs);
  assert(diagnosticLength>0 && diagnosticLength<sizeof(diagnostic));
  assert(std::string(diagnostic).find("mask=2")!=std::string::npos);
  std::cout<<"PASS M6 timeout record survives recovery and diagnostics do not overflow\n";
}
