#include <cassert>
#include <iostream>
#include "../TeleRC_4x_BTS7960_PWM_GlitchFilter/TeleRC_4x_BTS7960_PWM_GlitchFilter.ino"
void pulse(unsigned ch, uint16_t width, uint32_t end) {
  clockUs = end - width; levels[RC_IN_PIN[ch]] = 1; captureEdge(ch);
  clockUs = end; levels[RC_IN_PIN[ch]] = 0; captureEdge(ch);
}
void frame(uint32_t t, uint16_t width) {
  for (unsigned i=0;i<4;i++) pulse(i, width, t);
  clockUs=t; loop();
}
void outputsZero() {
  for(unsigned i=0;i<4;i++) {
    assert(currentCmd[i]==0);
    assert(duties[RPWM_PIN[i]]==0 && duties[LPWM_PIN[i]]==0);
  }
}
int main() {
  setup(); clockUs=10000; loop(); assert(!sourceEnabled); outputsZero();
  std::cout << "PASS startup without valid input stays stopped\n";
  for(uint32_t t=20000;t<=320000;t+=20000) frame(t,1500);
  assert(sourceEnabled);
  frame(340000,1800); assert(currentCmd[0]>0);
  pulse(0,100,345000); clockUs=345000; loop();
  assert(sourceEnabled && signalStops==0 && rejectedPulseCount[0]==1);
  assert(pulseWidthUs[0]==1800 && lastValidPulseUs[0]==340000);
  // A falling edge without a rising edge is rejected as well.
  clockUs=350000; levels[RC_IN_PIN[0]]=0; captureEdge(0); loop();
  assert(sourceEnabled && rejectedPulseCount[0]==2);
  std::cout << "PASS isolated invalid pulse/unmatched edge retains last valid command\n";
  // Keep other three channels valid; repeatedly corrupt channel 0.
  for(uint32_t t=360000;t<=480000;t+=20000) {
    pulse(0,2200,t); for(unsigned i=1;i<4;i++) pulse(i,1800,t);
    clockUs=t; loop(); assert(sourceEnabled);
  }
  clockUs=489999; snapshotInputs(); assert(channelFresh(0,clockUs));
  clockUs=490000; loop(); assert(!sourceEnabled && signalStops==1); outputsZero();
  assert(lastValidPulseUs[0]==340000);
  std::cout << "PASS continuous invalid pulses stop all motors at last-valid timeout\n";
  for(uint32_t t=500000;t<=800000;t+=20000) frame(t,1800);
  assert(!sourceEnabled && signalStops==1); outputsZero();
  std::cout << "PASS valid non-neutral signal cannot resume after timeout\n";
  for(uint32_t t=820000;t<=1100000;t+=20000) frame(t,1500);
  assert(!sourceEnabled);
  frame(1120000,1500); assert(sourceEnabled);
  std::cout << "PASS neutral recovery requires full 300 ms dwell\n";
  frame(1140000,1800); clockUs=1290000; loop();
  assert(!sourceEnabled && signalStops==2); outputsZero();
  std::cout << "PASS total signal loss stops all four outputs\n";
  // Unsigned freshness arithmetic across micros() rollover.
  for(unsigned i=0;i<4;i++) pulse(i,1500,0xfffff000U);
  snapshotInputs(); assert(channelFresh(0,0x1000U));
  assert(!channelFresh(0,uint32_t(0xfffff000U+RC_TIMEOUT_US)));
  std::cout << "PASS timer rollover preserves timeout\n";
  // Invalid pulses before the first valid pulse must not qualify as input.
  pulseValid[3]=false; pulse(3,100,2000000); snapshotInputs();
  assert(!channelFresh(3,2000000));
  std::cout << "PASS invalid-only startup cannot enable source\n";
  motorPwmReady=false; sourceEnabled=true; clockUs=2010000; loop(); outputsZero();
  assert(!sourceEnabled);
  std::cout << "PASS PWM initialization failure keeps all motors stopped\n";
  diagnosticOffset=diagnosticLength; lastDiagMs=0;
  serviceDiagnostics(clockUs); assert(diagnosticLength>0 && diagnosticLength<sizeof(diagnostic));
  assert(std::string(diagnostic).find("bad=")!=std::string::npos);
  for(int i=0;i<10;i++) serviceDiagnostics(clockUs);
  assert(diagnosticOffset==diagnosticLength);
  std::cout << "PASS diagnostics include rejection/stop/uptime/reset fields\n";
}
