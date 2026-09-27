/* SPDX-License-Identifier: MIT */
#pragma once
#define BEEPDATACOUNT 16
extern struct test_beep {unsigned mode,beep_data_load_loc,beep_data_curr_loc,beep_laskclk;} g_beep;
extern unsigned beep_data[BEEPDATACOUNT],beep_time[BEEPDATACOUNT];
void beep_lheventset(int);
void beep_hzset(unsigned);
void beep_modeset(void);
