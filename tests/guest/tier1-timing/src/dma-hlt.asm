; SPDX-License-Identifier: BSD-2-Clause
; Actual CPU opportunities; host-private debugger supplies dummy endpoint readiness.
bits 16
cpu 286
org 0
jmp start
times 510-($-$$) db 0
dw 0xaa55
start:
 cli
 cld
 mov ax,0x2800
 mov ss,ax
 mov sp,0x1800
 mov ax,0x2900
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,64
 rep stosw
 mov word [es:0],0x3144
 mov word [es:2],0x5448
 mov al,0xff
 out 2,al
 out 0x0a,al
 mov word [es:12],1
 mov ax,0x4200
 mov ds,ax
 mov cx,128
work:
 inc word [es:16]
 cmp byte [0],0xff
 jne next
 cmp byte [63],0xff
 je next
 inc word [es:18] ; Guest observed a partially transferred memory interval.
next:
 loop work
 mov word [es:12],2
 nop
 mov word [es:12],3
halt:
 hlt
 jmp halt
times 1022-($-$$) db 0
dw 0xaa55
