#pragma once
#include "Protocol.h"
#include <stdio.h>
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>
#include <esp_random.h>
namespace secure {
// TF2 source-route envelope. Discovery path is mutable under routing HMAC;
// RESPONSE/DATA/HELLO_ACK bind the complete chosen path with endpoint AEAD.
constexpr uint8_t MAX_HOPS=4,MAX_ROVERS=20,MAX_NODE_ID=200;
constexpr uint8_t HELLO=4,HELLO_ACK=5,DISCOVERY=1;
constexpr size_t HEAD=20,NONCE=12,TAG=16,MAC=16,MAX=HEAD+NONCE+mission::MAX_PLAIN+TAG+MAC;
static_assert(MAX<=255,"SX1262 payload limit");
inline bool mac(const uint8_t*key,const uint8_t*p,size_t n,uint8_t*out){
 uint8_t digest[32];auto info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!info||mbedtls_md_hmac(info,key,32,p,n,digest))return false;
 memcpy(out,digest,MAC);memset(digest,0,sizeof(digest));return true;
}
inline bool derive(const uint8_t*root,uint16_t fleet,uint8_t rover,uint8_t*out){
 if(!rover||rover>MAX_ROVERS)return false;
 char label[64];int n=snprintf(label,sizeof(label),"TeleRC-Fleet-v2-endpoint-%u-%u",unsigned(fleet),unsigned(rover));
 return mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),root,32,reinterpret_cast<const uint8_t*>(label),n,out)==0;
}
inline bool discovering(const uint8_t*p){return p[12]==DISCOVERY;}
inline bool shape(const uint8_t*p,size_t n){
 if(n<HEAD+NONCE+TAG+MAC||n>MAX||p[0]!='T'||p[1]!='F'||p[2]!=2||p[3]<1||p[3]>HELLO_ACK||
    p[7]>MAX_HOPS||p[8]>1||p[9]>p[7]||p[12]>DISCOVERY||p[18]!=MAX_HOPS||p[19]||
    mission::u16(p+10)>mission::MAX_PLAIN||n!=HEAD+NONCE+mission::u16(p+10)+TAG+MAC)return false;
 bool node=p[3]>=HELLO;
 if(node?(p[6]!=0||p[7]==0):(!p[6]||p[6]>MAX_ROVERS))return false;
 if(discovering(p)!=(p[3]==mission::SYNC||p[3]==HELLO))return false;
 if(p[8]!=(p[3]==mission::RESPONSE||p[3]==HELLO))return false;
 for(unsigned i=0;i<MAX_HOPS;++i){
  if(i<p[7]){if(!p[14+i]||p[14+i]>MAX_NODE_ID)return false;for(unsigned j=0;j<i;++j)if(p[14+i]==p[14+j])return false;}
  else if(p[14+i])return false;
 }
 if(discovering(p)&&(p[9]!=p[7]||p[13]!=(p[7]?p[13+p[7]]:0)))return false;
 return true;
}
inline void aadFor(const uint8_t*p,uint8_t*out){
 memcpy(out,p,HEAD);out[9]=out[13]=0;
 if(discovering(p)){out[7]=0;memset(out+14,0,MAX_HOPS);}
}
inline bool hopValid(const uint8_t*p,size_t n,const uint8_t*routeKey,uint16_t fleet){
 if(!shape(p,n)||mission::u16(p+4)!=fleet)return false;
 uint8_t tag[MAC];return mac(routeKey,p,n-MAC,tag)&&mission::equal(tag,p+n-MAC,MAC);
}
inline size_t seal(uint8_t*out,uint8_t kind,uint16_t fleet,uint8_t rover,const uint8_t*path,uint8_t count,
 const uint8_t*plain,size_t n,const uint8_t*key,const uint8_t*routeKey){
 if(n>mission::MAX_PLAIN||count>MAX_HOPS||!key)return 0;
 memset(out,0,HEAD);out[0]='T';out[1]='F';out[2]=2;out[3]=kind;mission::put16(out+4,fleet);out[6]=rover;out[7]=count;
 out[8]=(kind==mission::RESPONSE||kind==HELLO);out[12]=(kind==mission::SYNC||kind==HELLO)?DISCOVERY:0;
 out[9]=out[8]||out[12]?count:0;out[13]=out[12]?(count?path[count-1]:0):out[8]?255:0;
 if(count)memcpy(out+14,path,count);out[18]=MAX_HOPS;mission::put16(out+10,n);
 size_t size=HEAD+NONCE+n+TAG+MAC;if(!shape(out,size))return 0;
 esp_fill_random(out+HEAD,NONCE);uint8_t aad[HEAD];aadFor(out,aad);
 mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_crypt_and_tag(&ctx,MBEDTLS_GCM_ENCRYPT,n,out+HEAD,NONCE,aad,HEAD,plain,out+HEAD+NONCE,TAG,out+HEAD+NONCE+n);
 mbedtls_gcm_free(&ctx);if(result||!mac(routeKey,out,size-MAC,out+size-MAC))return 0;return size;
}
inline bool open(const uint8_t*p,size_t n,uint8_t*out,const uint8_t*key){
 if(!key||!shape(p,n))return false;
 size_t len=mission::u16(p+10);uint8_t aad[HEAD];aadFor(p,aad);
 mbedtls_gcm_context ctx;mbedtls_gcm_init(&ctx);int result=mbedtls_gcm_setkey(&ctx,MBEDTLS_CIPHER_ID_AES,key,256);
 if(!result)result=mbedtls_gcm_auth_decrypt(&ctx,len,p+HEAD,NONCE,aad,HEAD,p+HEAD+NONCE+len,TAG,p+HEAD+NONCE,out);
 mbedtls_gcm_free(&ctx);if(result){memset(out,0,mission::MAX_PLAIN);return false;}return true;
}
inline bool atBase(const uint8_t*p){return !discovering(p)&&p[8]==1&&p[9]==0&&p[13]==(p[7]?p[14]:255);}
inline bool atRover(const uint8_t*p){return !discovering(p)&&p[8]==0&&p[9]==p[7]&&p[13]==(p[7]?p[13+p[7]]:0);}
inline bool forNode(const uint8_t*p,uint8_t id){
 if(discovering(p)){for(unsigned i=0;i<p[7];++i)if(p[14+i]==id)return false;return p[7]<MAX_HOPS;}
 if(!p[8])return p[9]<p[7]&&p[14+p[9]]==id&&p[13]==(p[9]?p[13+p[9]]:0);
 return p[9]>0&&p[13+p[9]]==id&&p[13]==(p[9]==p[7]?255:p[14+p[9]]);
}
inline bool advance(uint8_t*p,size_t n,uint8_t id,const uint8_t*routeKey){
 if(!forNode(p,id))return false;
 if(discovering(p)){p[14+p[7]++]=id;p[9]=p[7];}
 else if(p[8])--p[9];else ++p[9];
 p[13]=id;return mac(routeKey,p,n-MAC,p+n-MAC);
}
}
