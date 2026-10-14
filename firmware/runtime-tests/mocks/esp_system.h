#pragma once
#include <cstdint>
constexpr int ESP_RST_BROWNOUT=9;
inline int esp_reset_reason(){return 1;}
inline uint32_t testRandom=123456;
inline uint32_t esp_random(){return ++testRandom;}
