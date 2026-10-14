#pragma once
#include "Arduino.h"
#include <map>
#define HTTP_GET 1
#define HTTP_POST 2
struct WebServer {
 std::map<std::string,String> args;bool auth=true;int code=0;String body;
 WebServer(int){}bool authenticate(const char*,const char*){return auth;}
 void requestAuthentication(){code=401;}void on(const char*,int,void(*)()){}
 void begin(){}void handleClient(){}String arg(const char*p){return args[p];}
 void sendHeader(const char*,const char*){}void send(int c,const char*,String s){code=c;body=s;}
};
