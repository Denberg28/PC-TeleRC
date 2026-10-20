#pragma once
#include <openssl/hmac.h>
#define MBEDTLS_MD_SHA256 1
using mbedtls_md_info_t=int;
inline const mbedtls_md_info_t*mbedtls_md_info_from_type(int){static int x;return &x;}
inline int mbedtls_md_hmac(const mbedtls_md_info_t*,const unsigned char*k,size_t kn,const unsigned char*p,size_t n,unsigned char*out){unsigned len=0;return HMAC(EVP_sha256(),k,kn,p,n,out,&len)&&len==32?0:-1;}
