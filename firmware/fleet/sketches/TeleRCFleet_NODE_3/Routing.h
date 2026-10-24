#pragma once
#include "Protocol.h"
namespace mesh {
// Device IDs are unrelated to path position. Bound active airtime, not ID count.
constexpr uint8_t MAX_NODE=200, MAX_HOPS=2;
constexpr uint32_t DISCOVERY_MS=5000, NODE_DISCOVERY_MS=3000, ROUTE_MS=30000, MANUAL_CYCLE_MS=350;
struct Route {
 uint8_t n=0,id[MAX_HOPS]={};
 bool valid()const{if(n>MAX_HOPS)return false;for(unsigned i=0;i<MAX_HOPS;++i){if(i<n){if(!id[i]||id[i]>MAX_NODE)return false;for(unsigned j=0;j<i;++j)if(id[j]==id[i])return false;}else if(id[i])return false;}return true;}
 bool operator==(const Route&b)const{return n==b.n&&mission::equal(id,b.id,MAX_HOPS);}
 bool operator!=(const Route&b)const{return !(*this==b);}
 bool contains(uint8_t node)const{if(n>MAX_HOPS)return false;for(unsigned i=0;i<n;++i)if(id[i]==node)return true;return false;}
 int stage(uint8_t node,bool reverse)const{if(n>MAX_HOPS)return -1;for(unsigned i=0;i<n;++i)if(id[i]==node)return reverse?int(n-1-i):int(i);return -1;}
 bool append(uint8_t node){if(!node||node>MAX_NODE||n>=MAX_HOPS||contains(node))return false;id[n++]=node;return true;}
};
struct Link {
 Route path;bool known=false;uint8_t successes=0;uint32_t at=0,worstRtt=0,samples[3]={};uint8_t cursor=0;
 void resetSamples(){successes=0;worstRtt=0;cursor=0;memset(samples,0,sizeof(samples));}
 void clear(){known=false;resetSamples();}
 bool observe(const Route&p,uint32_t now,uint32_t rtt){
  bool changed=!known||p!=path;
  if(changed){path=p;known=true;resetSamples();}
  samples[cursor]=rtt;cursor=(cursor+1)%3;if(successes<3)++successes;worstRtt=0;for(auto sample:samples)if(sample>worstRtt)worstRtt=sample;at=now;return changed;
 }
 bool fresh(uint32_t now)const{return known&&uint32_t(now-at)<ROUTE_MS;}
 bool qualified(uint32_t now)const{return fresh(now)&&successes>=3;}
 bool manual(uint32_t now,uint32_t dataAirMs)const{return qualified(now)&&worstRtt+(path.n+1)*dataAirMs+2*path.n+20<=MANUAL_CYCLE_MS;}
};
inline uint32_t contention(const uint8_t*nonce,uint8_t node){
 uint32_t hash=2166136261u;for(unsigned i=0;i<12;++i)hash=(hash^nonce[i])*16777619u;
 hash=(hash^node)*16777619u;
 // Avalanche the high bits before choosing a slot: FNV's low four bits alone
 // would make IDs differing by 16 collide on every retry, regardless of nonce.
 hash^=hash>>16;hash*=0x7feb352du;hash^=hash>>15;hash*=0x846ca68bu;hash^=hash>>16;
 return 8+(hash%16)*12;
}
}
