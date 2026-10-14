#pragma once
#include "Arduino.h"
struct Preferences{
 bool begin(const char*,bool){return true;}
 String getString(const char*,const char* d){return d;}
 size_t putString(const char*,const String& s){return s.length();}
 void end(){}
};
