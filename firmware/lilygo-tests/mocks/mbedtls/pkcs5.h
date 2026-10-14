#pragma once
#include "md.h"
#include <openssl/evp.h>
inline int mbedtls_pkcs5_pbkdf2_hmac_ext(int,const unsigned char*p,size_t pn,
 const unsigned char*s,size_t sn,unsigned int iterations,uint32_t n,unsigned char*out){
 return PKCS5_PBKDF2_HMAC(reinterpret_cast<const char*>(p),int(pn),s,int(sn),int(iterations),EVP_sha256(),int(n),out)==1?0:-1;
}
