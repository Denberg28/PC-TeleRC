#pragma once
#include <cstddef>
constexpr int MBEDTLS_MD_SHA256=0;
inline const void* mbedtls_md_info_from_type(int){return nullptr;}
inline int mbedtls_md_hmac(const void*,const unsigned char*,size_t,const unsigned char*,size_t,unsigned char*){return -1;}
