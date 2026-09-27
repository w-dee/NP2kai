/* SPDX-License-Identifier: MIT */
#pragma once
#include <nevent.h>
#include <io/pit.h>
#include <io/pic.h>
extern _PIT pit;
extern _PIC pic;
extern struct test_gdc {int vsyncint;} gdc;
typedef void (*IOOUT)(UINT,REG8);
typedef REG8 (*IOINP)(UINT);
static inline void iocore_attachsysoutex(UINT p,UINT m,const IOOUT *f,UINT n)
{(void)p;(void)m;(void)f;(void)n;}
static inline void iocore_attachsysinpex(UINT p,UINT m,const IOINP *f,UINT n)
{(void)p;(void)m;(void)f;(void)n;}

extern struct test_rs232c {unsigned mul,rawmode;} rs232c;
void rs232c_callback(void);
void rs232c_open(void);
static inline void iocore_attachout(UINT p,IOOUT f){(void)p;(void)f;}
static inline void iocore_attachinp(UINT p,IOINP f){(void)p;(void)f;}
