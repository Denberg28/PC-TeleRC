#pragma once
#include "Arduino.h"
struct Preferences {
 inline static std::vector<uint8_t> saved;
 bool begin(const char*,bool){return true;}String getString(const char*,const char*){return "test-password-123";}
 void putString(const char*,String){}void end(){}
 size_t getBytesLength(const char*){return saved.size();}
 size_t getBytes(const char*,void*p,size_t n){if(saved.size()!=n)return 0;memcpy(p,saved.data(),n);return n;}
 size_t putBytes(const char*,const void*p,size_t n){saved.assign((const uint8_t*)p,(const uint8_t*)p+n);return n;}
};
