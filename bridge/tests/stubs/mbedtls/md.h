#pragma once
// Host tests use OpenSSL's real HMAC-SHA256; embedded builds use ESP32 mbedTLS.
#include <openssl/hmac.h>
#define MBEDTLS_MD_SHA256 1
inline const EVP_MD *mbedtls_md_info_from_type(int){return EVP_sha256();}
inline int mbedtls_md_hmac(const EVP_MD*md,const unsigned char*key,size_t keyLen,const unsigned char*data,size_t n,unsigned char*out){unsigned int length=0;return HMAC(md,key,int(keyLen),data,n,out,&length)&&length==32?0:-1;}
