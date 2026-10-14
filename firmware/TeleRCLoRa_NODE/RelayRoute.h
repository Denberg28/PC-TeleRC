#pragma once
#include "SketchSettings.h"
#include "MeshCore.h"
namespace relay {
// Ordered chain: BASE(1), NODE1(3), NODE2(4), ROVER(2).
// Each packet can travel only toward its destination, once per node/token.
inline bool addressed(const mesh::Packet&p){
 if(p.network!=1||p.limit!=settings::LEGS)return false;
 const bool poll=p.kind==mesh::POLL;
 if(poll?(p.origin!=2||p.dest!=1):(p.kind!=mesh::COMMAND||p.origin!=1||p.dest!=2))return false;
 uint16_t sender;uint8_t hops;
 if(TELERC_ROLE==1){if(!poll)return false;sender=settings::RELAYS?settings::nodeId(1):2;hops=1;}
 else if(TELERC_ROLE==3){if(poll)return false;sender=settings::RELAYS?settings::nodeId(settings::RELAYS):1;hops=1;}
 else if(poll){sender=settings::NODE_INDEX<settings::RELAYS?settings::nodeId(settings::NODE_INDEX+1):2;hops=settings::NODE_INDEX+1;}
 else {sender=settings::NODE_INDEX==1?1:settings::nodeId(settings::NODE_INDEX-1);hops=settings::RELAYS+2-settings::NODE_INDEX;}
 return p.sender==sender&&p.hops==hops;
}
inline bool forward(mesh::Packet&p){
 if(TELERC_ROLE!=2||!addressed(p)||p.hops<=1)return false;
 --p.hops;p.sender=settings::SELF;return true;
}
}
