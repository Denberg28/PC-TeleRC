#pragma once
#include "Arduino.h"
#include <map>
#include <functional>
constexpr int HTTP_GET=0,HTTP_POST=1;
struct WebServer {
 std::map<std::string,std::function<void()>> routes;std::map<std::string,String> arguments;
 int status=0;String body;bool running=false;
 explicit WebServer(int){}
 void on(const char*p,int method,std::function<void()>f){routes[std::to_string(method)+p]=f;}
 String arg(const char*key){return arguments[key];}
 void sendHeader(const char*,const char*){}
 void send(int n,const char*,const String&s){status=n;body=s;}
 void begin(){running=true;}void handleClient(){}
 void call(const char*path,int method){routes.at(std::to_string(method)+path)();}
};
