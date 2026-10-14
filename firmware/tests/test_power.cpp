#include <cassert>
#include <iostream>
#include "../TeleRC_4x_BTS7960_PWM_GlitchFilter/TeleRC_4x_BTS7960_PWM_GlitchFilter.ino"
void pulse(unsigned ch, uint16_t width, uint32_t end) {
  clockUs=end-width; levels[RC_IN_PIN[ch]]=1; captureEdge(ch);
  clockUs=end; levels[RC_IN_PIN[ch]]=0; captureEdge(ch);
  clockUs=end+RC_EDGE_FILTER_US; snapshotInputs();
}
void tick(uint32_t t, uint16_t width) {
  if(t%20000==0) for(unsigned i=0;i<4;i++)pulse(i,width,t);
  clockUs=t;loop();
}
int main(){
  setup();
  for(uint32_t t=5000;t<=340000;t+=5000)tick(t,1500);
  assert(sourceEnabled);
  int last=0;
  for(uint32_t t=345000;t<=780000;t+=5000){
    tick(t,2000);
    assert(currentCmd[0]-last<=8);
    for(unsigned i=1;i<4;i++) assert(currentCmd[i]==currentCmd[0]);
    last=currentCmd[0];
  }
  assert(last==255);
  assert(slewToward(0, 255)==8);
  int response=0;
  for(int i=0;i<31;i++)response=slewToward(response,255);
  assert(response==248);
  assert(slewToward(response,255)==255);
  std::cout<<"PASS immediate first step; full-duty ramp exactly 32 ticks (~160 ms)\n";
  uint32_t firstZero=0, firstReverse=0;
  for(uint32_t t=785000;t<=1100000;t+=5000){
    tick(t,1000);
    if(!firstZero && currentCmd[0]==0)firstZero=t;
    if(!firstReverse && currentCmd[0]<0)firstReverse=t;
    for(unsigned i=0;i<4;i++) assert(!(duties[RPWM_PIN[i]] && duties[LPWM_PIN[i]]));
  }
  assert(firstZero && firstReverse-firstZero==CONTROL_PERIOD_US);
  std::cout<<"PASS reversal crosses zero then drives next tick; no added dwell or dual PWM\n";
  // A 60 ms delayed update with valid inputs must not latch off or catch up.
  const int beforeJitter=currentCmd[0];
  for(unsigned i=0;i<4;i++)pulse(i,1800,1160000);
  clockUs=1160000;loop();
  assert(sourceEnabled && loopStops==0);
  assert(abs(currentCmd[0]-beforeJitter)<=DECEL_STEP);
  std::cout<<"PASS 60 ms scheduler jitter keeps control active without catch-up burst\n";
  // A full 150 ms control-loop outage still stops, even with fresh ISR input.
  for(unsigned i=0;i<4;i++)pulse(i,1800,1310000);
  clockUs=1310000;loop();
  assert(!sourceEnabled && loopStops==1);
  for(unsigned i=0;i<4;i++)assert(currentCmd[i]==0);
  for(uint32_t t=1315000;t<=1500000;t+=5000)tick(t,1800);
  assert(!sourceEnabled);
  std::cout<<"PASS late control loop latches off despite fresh pulses\n";
  for(uint32_t t=1505000;t<=1840000;t+=5000)tick(t,1500);
  assert(sourceEnabled);
  bootResetReason=ESP_RST_BROWNOUT;
  assert(std::string(resetName())=="brownout");
  diagnosticOffset=diagnosticLength;lastDiagMs=0;serviceDiagnostics(clockUs);
  assert(std::string(diagnostic).find("brownout")!=std::string::npos);
  std::cout<<"PASS neutral recovery and explicit brownout diagnostics\n";
}

