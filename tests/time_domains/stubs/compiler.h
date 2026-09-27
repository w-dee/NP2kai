/* SPDX-License-Identifier: MIT */
#ifndef TEST_TIME_COMPILER_H
#define TEST_TIME_COMPILER_H
#include <stdint.h>
#include <limits.h>
#include <string.h>
typedef int32_t SINT32;
typedef uint32_t UINT32;
typedef int64_t SINT64;
typedef uint64_t UINT64;
typedef unsigned int UINT;
typedef uint8_t UINT8;
typedef intptr_t INTPTR;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define INLINE inline __attribute__((always_inline))
#endif
