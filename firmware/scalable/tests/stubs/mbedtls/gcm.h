#pragma once
// Host tests only: same AES-256-GCM contract, implemented by OpenSSL.
#include <openssl/evp.h>
#include <cstring>
#define MBEDTLS_CIPHER_ID_AES 1
#define MBEDTLS_GCM_ENCRYPT 1
struct mbedtls_gcm_context {unsigned char key[32];};
inline void mbedtls_gcm_init(mbedtls_gcm_context*c){memset(c,0,sizeof(*c));}
inline void mbedtls_gcm_free(mbedtls_gcm_context*c){memset(c,0,sizeof(*c));}
inline int mbedtls_gcm_setkey(mbedtls_gcm_context*c,int,const unsigned char*k,unsigned bits){if(bits!=256)return -1;memcpy(c->key,k,32);return 0;}
inline int mbedtls_gcm_crypt_and_tag(mbedtls_gcm_context*c,int,size_t n,const unsigned char*iv,size_t ivn,const unsigned char*aad,size_t an,const unsigned char*in,unsigned char*out,size_t tn,unsigned char*tag){
 auto*x=EVP_CIPHER_CTX_new();int used=0,end=0;
 int ok=x&&EVP_EncryptInit_ex(x,EVP_aes_256_gcm(),nullptr,nullptr,nullptr)==1&&EVP_CIPHER_CTX_ctrl(x,EVP_CTRL_GCM_SET_IVLEN,ivn,nullptr)==1&&EVP_EncryptInit_ex(x,nullptr,nullptr,c->key,iv)==1&&EVP_EncryptUpdate(x,nullptr,&used,aad,an)==1&&EVP_EncryptUpdate(x,out,&used,in,n)==1&&EVP_EncryptFinal_ex(x,out+used,&end)==1&&EVP_CIPHER_CTX_ctrl(x,EVP_CTRL_GCM_GET_TAG,tn,tag)==1;
 EVP_CIPHER_CTX_free(x);return ok?0:-1;
}
inline int mbedtls_gcm_auth_decrypt(mbedtls_gcm_context*c,size_t n,const unsigned char*iv,size_t ivn,const unsigned char*aad,size_t an,const unsigned char*tag,size_t tn,const unsigned char*in,unsigned char*out){
 auto*x=EVP_CIPHER_CTX_new();int used=0,end=0;
 int ok=x&&EVP_DecryptInit_ex(x,EVP_aes_256_gcm(),nullptr,nullptr,nullptr)==1&&EVP_CIPHER_CTX_ctrl(x,EVP_CTRL_GCM_SET_IVLEN,ivn,nullptr)==1&&EVP_DecryptInit_ex(x,nullptr,nullptr,c->key,iv)==1&&EVP_DecryptUpdate(x,nullptr,&used,aad,an)==1&&EVP_DecryptUpdate(x,out,&used,in,n)==1&&EVP_CIPHER_CTX_ctrl(x,EVP_CTRL_GCM_SET_TAG,tn,const_cast<unsigned char*>(tag))==1&&EVP_DecryptFinal_ex(x,out+used,&end)==1;
 EVP_CIPHER_CTX_free(x);return ok?0:-1;
}
