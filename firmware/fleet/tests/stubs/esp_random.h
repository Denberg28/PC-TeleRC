#pragma once
#include <openssl/rand.h>
#include <cstdlib>
inline void esp_fill_random(void*p,size_t n){if(RAND_bytes(static_cast<unsigned char*>(p),n)!=1)std::abort();}

inline uint32_t esp_random(){uint32_t n;esp_fill_random(&n,sizeof(n));return n;}
