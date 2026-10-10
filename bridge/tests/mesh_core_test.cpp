#include <cassert>
#include <iostream>
#include "MeshCore.h"
static void rc(uint8_t*out,uint16_t a,uint16_t b){
 memset(out,0,26);out[0]=0xfe;out[1]=18;out[3]=255;out[4]=190;out[5]=70;
 for(int i=0;i<8;++i)mesh::put16(out+6+2*i,i==0?a:i==1?b:65535);
 out[22]=out[23]=1;telerc::CommandMailbox::checksumRc(out);
}
int main(){
 uint8_t key[32]={1},wrong[32]={2},encoded[mesh::MAX];
 mesh::Packet p;p.kind=mesh::POLL;p.network=1;p.origin=2;p.dest=1;p.sender=2;p.hops=p.limit=3;p.token=123;
 p.n=96;memset(p.body,9,p.n);size_t n=mesh::seal(p,key,encoded);assert(n==mesh::MAX);
 mesh::Packet q;assert(mesh::open(encoded,n,key,q));assert(q.token==123&&q.n==96);
 assert(!mesh::open(encoded,n,wrong,q));
 for(size_t i=0;i<n;++i){encoded[i]^=1;assert(!mesh::open(encoded,n,key,q));encoded[i]^=1;}
 assert(!mesh::open(encoded,n-1,key,q));p.hops=0;assert(!mesh::seal(p,key,encoded));p.hops=3;
 mesh::Seen seen;assert(seen.admit(p,100));assert(!seen.admit(p,101));p.kind=mesh::COMMAND;assert(seen.admit(p,102));p.kind=mesh::POLL;assert(seen.admit(p,4101));
 // A three-leg request traverses two relays; TTL cannot reach a fourth leg.
 mesh::Packet forwarded=p;--forwarded.hops;forwarded.sender=3;assert(mesh::seal(forwarded,key,encoded));assert(mesh::open(encoded,n,key,q));assert(q.hops==2);
 --q.hops;q.sender=4;assert(mesh::seal(q,key,encoded));assert(mesh::open(encoded,n,key,forwarded));assert(forwarded.hops==1);
 mesh::Challenge c;c.issue(111,100);assert(!c.consume(112,101));assert(c.consume(111,450));assert(!c.consume(111,451));c.issue(111,100);assert(!c.consume(111,451));
 c.issue(7,UINT32_MAX-100);assert(c.consume(7,50)); // millis rollover
 uint8_t frame[26];mesh::Safety safe;
 rc(frame,1500,1800);assert(!safe.rc(frame,26,10));assert(!safe.ready);
 rc(frame,1500,1500);assert(safe.rc(frame,26,20));assert(safe.centered(20));
 rc(frame,1700,1800);assert(safe.rc(frame,26,21));assert(!safe.centered(21));
 rc(frame,1500,65535);assert(safe.rc(frame,26,300));assert(!safe.expired(520));assert(safe.expired(521)); // throttle still stale
 safe.latch();assert(!safe.rc(frame,26,522));rc(frame,1500,1500);assert(safe.rc(frame,26,523));
 mesh::put16(frame+10,1600);telerc::CommandMailbox::checksumRc(frame);assert(!safe.rc(frame,26,524)); // reserved CH3 cannot leak
 rc(frame,0,65535);assert(safe.rc(frame,26,525));assert(!safe.ready&&safe.owned==0);
 rc(frame,1500,1500);assert(safe.rc(frame,26,UINT32_MAX-100));assert(!safe.expired(398));assert(safe.expired(399));
 telerc::CommandMailbox mailbox;rc(frame,1500,1800);assert(mailbox.accept(frame,26,10));uint8_t bundle[96];assert(mailbox.take(bundle,211)==0); // no queued stale drive
 assert(mailbox.accept(frame,26,212));assert(mailbox.take(bundle,213)==27);assert(mailbox.take(bundle,214)==0);
 // Sparse updates cannot refresh untouched drive, through the actual mailbox.
 rc(frame,1500,1800);assert(mailbox.accept(frame,26,300));rc(frame,1600,65535);assert(mailbox.accept(frame,26,499));assert(mailbox.take(bundle,501)==27);assert(mesh::u16(bundle+1+8)==65535);
 mesh::MavParser parser;rc(frame,1500,1500);bool completed=false;for(auto b:frame)completed=parser.feed(b,100);assert(completed&&parser.total==26);
 assert(!parser.feed(0xfe,200));assert(!parser.feed(18,200));assert(!parser.feed(0xff,221)); // partial expiry
 std::cout<<"Mesh authentication, hops, duplicate cache, challenge, watchdog, sparse mailbox: PASS\n";
}
