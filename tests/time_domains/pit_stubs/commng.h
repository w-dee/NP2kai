/* SPDX-License-Identifier: MIT */
#pragma once
typedef struct test_comm *COMMNG;
struct test_comm {void (*msg)(COMMNG,unsigned,INTPTR);};
#define COMMSG_CHANGESPEED 1
#define COMMSG_CHANGEMODE 2
