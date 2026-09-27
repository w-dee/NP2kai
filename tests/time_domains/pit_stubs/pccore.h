/* SPDX-License-Identifier: MIT */
#pragma once
typedef struct {int unused;} NP2CFG;
extern struct test_pccore {UINT32 realclock;UINT multiple,cpumode;UINT8 dipsw[3];} pccore;
extern struct test_pcstat {UINT8 screendispflag;} pcstat;

#define CPUMODE_8MHZ 1
