/* SPDX-License-Identifier: MIT */
#pragma once
#include <io/artic.h>
extern _ARTIC artic;
extern void (*test_out[256])(UINT, REG8);
extern REG8 (*test_in[256])(UINT);
static inline void iocore_attachout(UINT p,void (*f)(UINT,REG8)) {test_out[p]=f;}
static inline void iocore_attachinp(UINT p,REG8 (*f)(UINT)) {test_in[p]=f;}
