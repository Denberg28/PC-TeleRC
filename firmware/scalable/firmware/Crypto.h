#pragma once
#include "Protocol.h"
#include "Routing.h"
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>
#include <esp_random.h>
namespace secure {
// TU v2: fixed 20-byte header. Count, ordered node IDs, discovery flag and
// transaction ID replace the v1 two-bit mask. No v1 packet is accepted.
constexpr size_t HEAD=20, NONCE=12, TAG=16, MAC=16, MAX=HEAD+NONCE+mission::MAX_PLAIN+TAG+MAC;
static_assert(MAX<=255,"SX1262 payload limit");
inline mesh::Route route(const uint8_t*p){mesh::Route r;r.n=p[7];memcpy(r.id,p+12,mesh::MAX_HOPS);return r;}
inline bool discovery(const uint8_t*p){return p[14]==1;}
inline bool mac(const uint8_t*key,const uint8_t*p,size_t n,uint8_t*out){
 uint8_t digest[32];auto info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!info||mbedtls_md_hmac(info,key,32,p,n,digest))return false;
 memcpy(out,digest,MAC);memset(digest,0,sizeof(digest));return true;
}
inline void aad(const uint8_t*p,uint8_t*out){memcpy(out,p,HEAD);out[9]=0;
 // Only discovery's accumulated route is mutable by relays. Discovery carries
 // a read-only health query. All response/command routes remain AEAD-bound.
 if(discovery(p)){out[7]=0;memset(out+12,0,mesh::MAX_HOPS);}
}
inline bool hopValid(const uint8_t*p,size_t n,const uint8_t*key,uint16_t fleet){
 if(n<HEAD+NONCE+TAG+MAC||n>MAX||p[0]!='T'||p[1]!='U'||p[2]!=2||p[3]<1||p[3]>3||
 mission::u16(p+4)!=fleet||!p[6]||p[6]>20||p[8]>1||p[9]>p[7]||!route(p).valid()||p[14]>1||p[15]!=mesh::MAX_HOPS||
 (discovery(p)&&(p[3]!=mission::SYNC||p[8]||p[9]!=p[7]))||
 mission::u16(p+10)>mission::MAX_PLAIN||n!=HEAD+NONCE+mission::u16(p+10)+TAG+MAC)return false;
 uint8_t tag[MAC];return mac(key,p,n-MAC,tag)&&mission::equal(tag,p+n-MAC,MAC);
}
inline size_t seal(uint8_t*out,uint8_t kind,uint16_t fleet,uint8_t rover,const mesh::Route&r,uint8_t dir,
 const uint8_t*plain,size_t n,const uint8_t*key,const uint8_t*routeKey,bool discover=false,uint32_t transaction=0){
 if(n>mission::MAX_PLAIN||!r.valid()||(discover&&(kind!=mission::SYNC||dir)))return 0;
 memset(out,0,HEAD);out[0]='T';out[1]='U';out[2]=2;out[3]=kind;mission::put16(out+4,fleet);out[6]=rover;
 out[7]=r.n;out[8]=dir;mission::put16(out+10,n);memcpy(out+12,r.id,mesh::MAX_HOPS);out[14]=discover;out[15]=mesh::MAX_HOPS;
 for(unsigned i=0;i<4;++i)out[16+i]=transaction>>(8*i);
 esp_fill_random(out+HEAD,NONCE);uint8_t auth[HEAD];aad(out,auth);mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);
 int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,n,out+HEAD,NONCE,auth,HEAD,plain,out+HEAD+NONCE,TAG,out+HEAD+NONCE+n);
 mbedtls_gcm_free(&ctx);size_t size=HEAD+NONCE+n+TAG+MAC;
 if(result||!mac(routeKey,out,size-MAC,out+size-MAC))return 0;return size;
}
inline bool open(const uint8_t*p,size_t size,uint8_t*out,const uint8_t*key){
 if(size<HEAD+NONCE+TAG+MAC||size>MAX)return false;
 size_t n=mission::u16(p+10);if(n>mission::MAX_PLAIN||size!=HEAD+NONCE+n+TAG+MAC)return false;
 uint8_t auth[HEAD];aad(p,auth);mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);
 int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_auth_decrypt(&ctx,n,p+HEAD,NONCE,auth,HEAD,p+HEAD+NONCE+n,TAG,p+HEAD+NONCE,out);
 mbedtls_gcm_free(&ctx);if(result){memset(out,0,mission::MAX_PLAIN);return false;}return true;
}
inline bool advance(uint8_t*p,size_t n,const uint8_t*key){if(p[9]>=p[7])return false;++p[9];return mac(key,p,n-MAC,p+n-MAC);}
inline bool extend(uint8_t*p,size_t n,uint8_t node,const uint8_t*key){
 auto r=route(p);if(!discovery(p)||!r.append(node))return false;
 p[7]=p[9]=r.n;memcpy(p+12,r.id,mesh::MAX_HOPS);return mac(key,p,n-MAC,p+n-MAC);
}
}
