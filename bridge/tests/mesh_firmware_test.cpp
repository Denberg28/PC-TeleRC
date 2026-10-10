#include <cassert>
#include <iostream>
#include "../TeleRCMesh/TeleRCMesh.ino"
static void resetRover(){
 cfg=Config{};cfg.role=ROVER;cfg.node=2;cfg.khz=915000;cfg.key[0]=1;
 safety.latch();stopPending=false;vehicle.tx.clear();vehicle.capacity=1024;
 commands.clear();clearQueue();radioOK=true;transmitting=scanning=false;
 testMs=1000;haveFc=true;fcAt=testMs;challenge.active=false;radioIRQ=false;
 pollAt=testMs;pollInFlight=false;seen=mesh::Seen{};for(auto&s:telemetry)s.n=0;
}
static void sendRc(uint16_t steer,uint16_t drive){
 uint8_t b[27];b[0]=26;makeRc(b+1,1500,2);mesh::put16(b+7,steer);mesh::put16(b+9,drive);telerc::CommandMailbox::checksumRc(b+1);
 acceptCommands(b,sizeof(b));
}
static void tickUntil(uint32_t end){
 while(testMs<end){++testMs;if(scanning||transmitting)radioIRQ=true;loop();}
}
int main(){
 resetRover();assert(validConfig(cfg));Config invalid=cfg;strcpy(invalid.wifi,"telerc");assert(!validConfig(invalid));invalid=cfg;invalid.role=RELAY;assert(!validConfig(invalid));
 sendRc(1500,1800);assert(vehicle.tx.empty()&&!safety.ready);
 sendRc(1500,1500);assert(vehicle.tx.size()==26&&safety.ready);sendRc(1700,1800);assert(safety.owned==3);
 testMs=1500;loop();assert(!safety.ready&&safety.owned==0);assert(vehicle.tx.size()==104); // 2 commands + neutral + release
 assert(mesh::u16(vehicle.tx.data()+52+6)==1500&&mesh::u16(vehicle.tx.data()+78+6)==0);
 vehicle.tx.clear();sendRc(1500,1800);assert(vehicle.tx.empty());sendRc(1500,1500);assert(vehicle.tx.size()==26);
 // A release and DISARM in one response must both survive.
 uint8_t stopBundle[69]={};stopBundle[0]=26;makeRc(stopBundle+1,0,3);stopBundle[27]=41;
 uint8_t*disarm=stopBundle+28;disarm[0]=0xfe;disarm[1]=33;disarm[3]=255;disarm[4]=190;disarm[5]=76;
 disarm[34]=0x90;disarm[35]=1;disarm[36]=disarm[37]=1;
 uint16_t crc=0xffff;for(int i=1;i<39;++i)crc=telerc::mavCrcByte(crc,disarm[i]);crc=telerc::mavCrcByte(crc,152);mesh::put16(disarm+39,crc);
 vehicle.tx.clear();acceptCommands(stopBundle,69);assert(vehicle.tx.size()==93&&!safety.ready);assert(vehicle.tx[52+5]==76);
 sendRc(1500,1500);
 // Congestion stops, latches, and retries only neutral/release.
 vehicle.tx.clear();vehicle.capacity=0;sendRc(1500,1800);assert(stopPending&&!safety.ready&&vehicle.tx.empty());
 vehicle.capacity=1024;testMs+=100;loop();assert(!stopPending&&vehicle.tx.size()==52);
 // Monitor-only stop never changes receiver overrides.
 resetRover();stopControl();assert(vehicle.tx.empty());
 // Stale FC heartbeat cannot admit commands; no synthetic heartbeat revives it.
 haveFc=false;sendRc(1500,1500);assert(vehicle.tx.empty());haveFc=true;
 // The dedicated motor has a GENERIC autopilot heartbeat, admitted only for that UART backend.
 uint8_t hb[17]={0xfe,9,0,1,1,0};hb[10]=10;hb[11]=0;hb[14]=3;
 crc=0xffff;for(int i=1;i<15;++i)crc=telerc::mavCrcByte(crc,hb[i]);crc=telerc::mavCrcByte(crc,50);mesh::put16(hb+15,crc);
 haveFc=false;takeVehicleFrame(hb,17);assert(!haveFc);cfg.backend=FRAMED_MOTOR;takeVehicleFrame(hb,17);assert(haveFc);cfg.backend=RAW_FC;
 // Complete radio command needs a matching live challenge and is consumed once.
 mesh::Packet p=makePacket(mesh::COMMAND,123);p.origin=p.sender=cfg.gateway;p.dest=cfg.node;p.n=27;p.body[0]=26;makeRc(p.body+1,1500,1);
 uint8_t encoded[mesh::MAX];size_t n=mesh::seal(p,cfg.key,encoded);radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();assert(vehicle.tx.empty());
 p.token=124;n=mesh::seal(p,cfg.key,encoded);challenge.issue(124,testMs,mesh::timing(cfg.hops).responseMs);radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();assert(vehicle.tx.size()==26&&!challenge.active);
 radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();assert(vehicle.tx.size()==26);
 // A valid but late direct response cannot enable motion or refresh ownership.
 resetRover();p.hops=p.limit=1;p.token=125;challenge.issue(p.token,testMs,90);
 testMs+=91;n=mesh::seal(p,cfg.key,encoded);radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();
 assert(vehicle.tx.empty()&&!safety.ready);
 // Direct scheduling is anchored to TX completion, not enqueue; no challenge
 // may be replaced while a valid response is still outstanding.
 resetRover();testMs=1099;sendPoll();assert(!queue[0].active);
 testMs=1100;sendPoll();assert(queue[0].active);pumpTx();assert(scanning);
 testMs=1102;radioIRQ=true;pumpRadio();assert(transmitting&&!challenge.active);
 testMs=1129;radioIRQ=true;pumpRadio();assert(!transmitting&&challenge.at==1129&&challenge.window==90&&pollAt==1129);
 testMs=1228;sendPoll();assert(!queue[0].active);
 testMs=1229;sendPoll();assert(queue[0].active);clearQueue();pollAt=1129;challenge.issue(126,1220,90);
 testMs=1310;sendPoll();assert(!queue[0].active);testMs=1311;sendPoll();assert(queue[0].active);
 resetRover();cfg.hops=2;testMs=1369;sendPoll();assert(!queue[0].active);
 testMs=1370;sendPoll();assert(queue[0].active);
 // A clear scan after a long busy deferral must not send a direct response
 // whose airtime would put its completion outside the 90 ms reply window.
 resetRover();cfg.role=GATEWAY;cfg.node=1;p=makePacket(mesh::COMMAND,127);p.n=27;
 p.body[0]=26;makeRc(p.body+1,1500,1);assert(enqueue(p,3));testMs+=60;pumpTx();
 size_t sent=radio.tx.size();radioIRQ=true;pumpRadio();assert(!transmitting&&!queue[0].active&&radio.tx.size()==sent);
 assert(enqueue(p,3));testMs+=3;pumpTx();radioIRQ=true;pumpRadio();assert(transmitting&&radio.tx.size()==sent+1);
 // Two missing direct refreshes keep a still-fresh command alive. Three
 // missing refreshes expire it before the fourth cycle; no automatic restart.
 resetRover();sendRc(1500,1500);testMs=1129;sendRc(1700,1800);tickUntil(1387);assert(safety.ready);
 tickUntil(1516);assert(safety.ready);tickUntil(1629);assert(!safety.ready&&safety.owned==0);
 vehicle.tx.clear();testMs=1645;sendRc(1700,1800);assert(vehicle.tx.empty());
 sendRc(1500,1500);assert(safety.ready&&vehicle.tx.size()==26);
 // Relay forwards at most once, authenticates a decremented budget, and never writes motor UART.
 resetRover();cfg.role=RELAY;cfg.node=3;cfg.hops=3;p.kind=mesh::POLL;p.origin=p.sender=cfg.rover;p.dest=cfg.gateway;p.hops=p.limit=3;p.token=999;p.n=0;
 n=mesh::seal(p,cfg.key,encoded);radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();assert(queue[0].active&&queue[0].p.hops==2&&queue[0].p.sender==3);
 radio.rx.assign(encoded,encoded+n);radioIRQ=true;pumpRadio();assert(!queue[1].active&&vehicle.tx.empty());
 // Channel scan does not stall loop/watchdog; defers busy channel without replay.
 testMs+=20;pumpTx();assert(scanning);radio.scanResult=RADIOLIB_LORA_DETECTED;radioIRQ=true;pumpRadio();assert(!scanning&&!transmitting&&queue[0].active);
 testMs+=30;pumpTx();radio.scanResult=RADIOLIB_CHANNEL_FREE;radioIRQ=true;pumpRadio();assert(transmitting&&!queue[0].active);radioIRQ=true;pumpRadio();assert(!transmitting);
 // Any receiver restart failure latches owned control OFF and emits stop.
 resetRover();sendRc(1500,1500);vehicle.tx.clear();radio.receiveResult=-1;assert(!restartRx());assert(!radioOK&&!safety.ready&&vehicle.tx.size()==52);radio.receiveResult=0;
 // Setup POST validates all fields; shared IDs and all-zero keys cannot activate RF.
 maintenance=true;csrf="token";cfg=Config{};web.args={{"csrf","token"},{"role","1"},{"node","1"},{"network","1"},{"gateway","1"},{"rover","2"},{"hops","3"},{"frequency_khz","915000"},{"power_dbm","2"},{"backend","0"},{"key",String(64,'0')}};
 save();assert(web.code==400);web.args["key"]=String("01")+String(62,'0');save();assert(web.code==200&&reboot);
 web.auth=false;save();assert(web.code==401);
 std::cout<<"Actual firmware command path, stop/retry, replay, relay, CAD, setup validation: PASS\n";
}
