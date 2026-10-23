#pragma once
// Generate private reusable network files once with tools/network.py init.
// Public examples intentionally keep RF disabled. Never publish generated keys.
#define PROVISIONED 0
#define FLEET_ID 271
#define FREQUENCY_MHZ 915.0f
#define POWER_DBM 2
#define SERVO_MASK 0
static const uint8_t ROUTE_KEY[32]={0};
#if ROLE != 3
static const uint8_t ENDPOINT_ROOT[32]={0};
#endif
