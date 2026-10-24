#pragma once
#include "Protocol.h"
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>
#include <esp_random.h>

namespace secure {
// Header 12 bytes: TU, version, kind, fleet LE16, rover, relays, direction,
// mutable stage, ciphertext length LE16. Stage is excluded from AEAD but is
// authenticated hop-by-hop by a distinct routing key; all other bytes are AAD.
constexpr size_t HEAD=12, NONCE=12, TAG=16, MAC=16, MAX=HEAD+NONCE+mission::MAX_PLAIN+TAG+MAC;
static_assert(MAX<=255,"SX1262 payload limit");
inline bool mac(const uint8_t*key,const uint8_t*p,size_t n,uint8_t*out){
 uint8_t digest[32];auto info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!info||mbedtls_md_hmac(info,key,32,p,n,digest))return false;
 memcpy(out,digest,MAC);memset(digest,0,sizeof(digest));return true;
}
inline unsigned hops(uint8_t mask){return unsigned(bool(mask&1))+unsigned(bool(mask&2));}
inline bool hopValid(const uint8_t*p,size_t n,const uint8_t*routeKey,uint16_t fleet,uint8_t relays){
 if(n<HEAD+NONCE+TAG+MAC||n>MAX||p[0]!='T'||p[1]!='U'||p[2]!=1||
    p[3]<1||p[3]>3||mission::u16(p+4)!=fleet||!p[6]||p[6]>20||p[7]>3||hops(p[7])>relays||p[8]>1||p[9]>hops(p[7])||
    mission::u16(p+10)>mission::MAX_PLAIN||n!=HEAD+NONCE+mission::u16(p+10)+TAG+MAC)return false;
 uint8_t tag[MAC];return mac(routeKey,p,n-MAC,tag)&&mission::equal(tag,p+n-MAC,MAC);
}
inline size_t seal(uint8_t*out,uint8_t kind,uint16_t fleet,uint8_t rover,uint8_t relays,uint8_t dir,
 const uint8_t*plain,size_t n,const uint8_t*key,const uint8_t*routeKey){
 if(n>mission::MAX_PLAIN)return 0;
 memset(out,0,HEAD);out[0]='T';out[1]='U';out[2]=1;out[3]=kind;mission::put16(out+4,fleet);
 out[6]=rover;out[7]=relays;out[8]=dir;mission::put16(out+10,n);
 esp_fill_random(out+HEAD,NONCE);mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);
 int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,n,out+HEAD,NONCE,out,HEAD,plain,out+HEAD+NONCE,TAG,out+HEAD+NONCE+n);
 mbedtls_gcm_free(&ctx);size_t size=HEAD+NONCE+n+TAG+MAC;
 if(result||!mac(routeKey,out,size-MAC,out+size-MAC))return 0;return size;
}
inline bool open(const uint8_t*p,size_t size,uint8_t*out,const uint8_t*key){
 if(size<HEAD+NONCE+TAG+MAC||size>MAX)return false;
 size_t n=mission::u16(p+10);if(n>mission::MAX_PLAIN||size!=HEAD+NONCE+n+TAG+MAC)return false;
 uint8_t aad[HEAD];memcpy(aad,p,HEAD);aad[9]=0;
 mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_auth_decrypt(&ctx,n,p+HEAD,NONCE,aad,HEAD,p+HEAD+NONCE+n,TAG,p+HEAD+NONCE,out);
 mbedtls_gcm_free(&ctx);if(result){memset(out,0,mission::MAX_PLAIN);return false;}return true;
}
inline bool advance(uint8_t*p,size_t n,const uint8_t*routeKey){++p[9];return mac(routeKey,p,n-MAC,p+n-MAC);}
}
