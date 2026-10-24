#pragma once
struct WireStub {
 void begin(int,int){}void setClock(int){}void setTimeOut(int){}
 void beginTransmission(int){}void write(int){}void write(const unsigned char*,size_t){}
 int endTransmission(){return 0;}
};inline WireStub Wire;
