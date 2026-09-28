; SPDX-License-Identifier: BSD-2-Clause
; Original DOS-free N5 fixture. Time control is host-private GDB instrumentation.
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
 xor ax,ax
 mov ds,ax
 mov word [0x54],handler
 mov [0x56],cs
 mov ax,0x2900
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,64
 rep stosw
 mov word [es:0],0x354e
 mov word [es:2],0x4d54
 mov al,0xff
 out 2,al
 out 0x0a,al
 mov dx,0xbfdb
 xor al,al
 out dx,al
 mov dx,0x7fdd
 out dx,al
 mov word [es:12],1
 mov cx,8192
work:
 inc word [es:16]
 loop work
 mov al,0x0a
 out 8,al
 in al,8
 mov [es:18],al
 mov word [es:12],2
 in al,8
 mov [es:20],al
 mov ax,[es:24]
 mov [es:22],ax
 mov al,0x7f
 out 2,al
 mov al,0xdf
 out 0x0a,al
 sti
 nop
wait_first:
 cmp word [es:24],1
 jb wait_first
 cli
 mov word [es:12],3
 mov dx,0x7fd9
 in al,dx
 mov [es:32],al
 mov word [es:12],4
 sti
 hlt
wake:
 cli
 mov word [es:34],0x1234
 mov word [es:12],5
 mov dx,0x7fdd
 mov al,0x10
 out dx,al
 mov ax,[es:24]
 mov [es:36],ax
 mov word [es:126],2
stop:
 hlt
 jmp stop
handler:
 push ax
 inc word [es:24]
 mov al,0x0b
 out 8,al
 in al,8
 mov [es:26],al
 mov al,0x20
 out 8,al
 out 0,al
 mov al,0x0b
 out 8,al
 in al,8
 mov [es:28],al
 pop ax
 iret
times 1022-($-$$) db 0
dw 0xaa55
