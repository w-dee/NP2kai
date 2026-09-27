/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <limits.h>
#include <string.h>
typedef int32_t SINT32; typedef uint32_t UINT32; typedef int64_t SINT64;
typedef uint64_t UINT64; typedef unsigned UINT; typedef uint8_t UINT8;
typedef uint16_t UINT16; typedef intptr_t INTPTR; typedef int BOOL;
typedef unsigned REG8;
#define TRUE 1
#define FALSE 0
#define INLINE inline __attribute__((always_inline))
#define IOOUTCALL
#define IOINPCALL
#define TRACEOUT(x) ((void)0)

#define ZeroMemory(p,n) memset(p,0,n)
#define LOW16(v) ((v)&65535)
