#pragma once
// Use tools/provision.py to generate complete matching sketches and private keys.
// An unprovisioned example must not transmit.
#define ROLE 3 // 1 BASE, 2 ROVER, 3 NODE
#define ROVER_ID 1 // 1..20; FC SYSID_THISMAV must match
#define NODE_INDEX 1 // 1 nearest BASE, 2 nearest ROVER
#define RELAY_COUNT 2 // same 0..2 on every participant
#define FLEET_ID 271
#define FREQUENCY_MHZ 915.0f
#define POWER_DBM 2
#define SERVO_MASK 0 // opt-in auxiliary outputs only; never motor channels
#define PROVISIONED 0
struct RoverKey { unsigned char id; unsigned char key[32]; };
static const unsigned char ROUTE_KEY[32]={0};
static const RoverKey ROVERS[]={{1,{0}}};
