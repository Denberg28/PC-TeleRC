#include <cassert>
#include "Runtime.h"
#include "fixtures.h"
int main(){
 setup();clockMs=10;mission::Gate g(1);mission::Mav frame;
 assert(frame.parse(fcHb,sizeof(fcHb))&&g.fromFc(frame,clockMs));
 assert(frame.parse(arm,sizeof(arm))&&!g.down(frame,clockMs));
 g.verifiedUpload=true;assert(g.down(frame,clockMs));
 assert(frame.parse(forceArm,sizeof(forceArm))&&!g.down(frame,clockMs));
 assert(frame.parse(foreignArm,sizeof(foreignArm))&&!g.down(frame,clockMs));
 assert(frame.parse(paramSet,sizeof(paramSet))==false); // never implement parameter writes
 assert(frame.parse(disarm,sizeof(disarm))&&g.down(frame,clockMs));
 assert(frame.parse(autoHb,sizeof(autoHb))&&g.fromFc(frame,clockMs));
 assert(frame.parse(disarm,sizeof(disarm))&&!g.down(frame,clockMs));
 if(ROLE==1){
  selected=1;replyProfile=unified::MISSION;
  for(unsigned i=0;i<20;++i){auto&p=peers[i];p.active=true;p.link.known=true;p.link.successes=3;p.link.at=clockMs;p.link.worstRtt=5;}
  assert(fleetBudget());
  for(auto&p:peers)p.link.worstRtt=500;
  assert(!fleetBudget());
  closePeer(2);assert(!peers[1].active&&peers[0].active);
 }
 assert(fc.tx.empty());
}
