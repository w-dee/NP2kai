/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <limits.h>
typedef uint64_t UINT64;
#include <string.h>
typedef int32_t SINT32; typedef uint32_t UINT32; typedef uint16_t UINT16; typedef uint8_t UINT8; typedef unsigned UINT; typedef unsigned REG8; typedef unsigned REG16;
#define INLINE inline
#define IOOUTCALL
#define IOINPCALL
#define ZeroMemory(p,n) memset(p,0,n)
