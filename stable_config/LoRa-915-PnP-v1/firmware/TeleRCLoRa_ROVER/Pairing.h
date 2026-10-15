#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <mbedtls/pkcs5.h>
namespace telerc {
constexpr unsigned PAIRING_ITERATIONS=10000;
constexpr char PAIRING_SALT[]="TeleRC-LoRa-Link-v1";
inline bool passwordKey(const char*password,size_t n,uint8_t*out){
 if(n<8||n>32)return false;
 for(size_t i=0;i<n;++i)if(uint8_t(password[i])<33||uint8_t(password[i])>126)return false;
 return mbedtls_pkcs5_pbkdf2_hmac_ext(MBEDTLS_MD_SHA256,
  reinterpret_cast<const unsigned char*>(password),n,
  reinterpret_cast<const unsigned char*>(PAIRING_SALT),sizeof(PAIRING_SALT)-1,
  PAIRING_ITERATIONS,32,out)==0;
}
inline bool frequencyKHz(const char*s,uint32_t&out){
 if(!s||!*s||strlen(s)>7)return false;
 uint32_t whole=0,fraction=0;unsigned before=0,after=0;bool point=false;
 for(;*s;++s){
  if(*s=='.'&&!point){point=true;continue;}
  if(*s<'0'||*s>'9')return false;
  if(!point){if(++before>3)return false;whole=whole*10+unsigned(*s-'0');}
  else {if(++after>3)return false;fraction=fraction*10+unsigned(*s-'0');}
 }
 if(!before||(point&&!after))return false;
 while(after++<3)fraction*=10;
 out=whole*1000+fraction;
 return (out>=400250&&out<=519750)||(out>=830250&&out<=944750);
}
}
