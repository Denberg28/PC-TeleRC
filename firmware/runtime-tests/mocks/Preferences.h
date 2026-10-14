#pragma once
#include "Arduino.h"
#include <map>
struct Preferences {
 inline static std::map<std::string,std::vector<uint8_t>> storage;
 inline static bool fail=false;std::string ns;
 bool begin(const char*n,bool){ns=n;return !fail;}void end(){}
 size_t getBytesLength(const char*k){return storage[ns+"/"+k].size();}
 size_t getBytes(const char*k,void*p,size_t n){auto&b=storage[ns+"/"+k];if(b.size()!=n)return 0;memcpy(p,b.data(),n);return n;}
 size_t putBytes(const char*k,const void*p,size_t n){if(fail)return 0;storage[ns+"/"+k].assign((const uint8_t*)p,(const uint8_t*)p+n);return n;}
 uint8_t getUChar(const char*k,uint8_t fallback){auto&b=storage[ns+"/"+k];return b.size()==1?b[0]:fallback;}
 size_t putUChar(const char*k,uint8_t v){return putBytes(k,&v,1);}
};
