; SPDX-License-Identifier: BSD-2-Clause
; Original DOS-free compatibility fixture. Host fake control is debugger-only.
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
 mov word [0x20],handler
 mov [0x22],cs
 mov ax,0x2900
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,64
 rep stosw
 mov word [es:0],0x4950
 mov word [es:2],0x4350
 mov word [es:4],1
 mov word [es:6],128
 mov word [es:8],RUN_MODE
 mov word [es:10],PROFILE
 mov word [es:122],0xa55a
 mov al,0xff
 out 2,al
 mov al,0x30
 out 0x77,al
 mov al,100
 out 0x71,al
 xor al,al
 out 0x71,al
 mov word [es:16],0x30
 mov word [es:18],100
 mov word [es:12],1
 call readword
 mov [es:20],ax
 mov cx,8192
 xor bx,bx
work:
 inc bx
 loop work
 mov [es:40],bx
 mov word [es:12],2
 call readword
 mov [es:24],ax
 mov word [es:12],3
 xor al,al
 out 0x77,al
 call readword
 mov [es:26],ax
 mov al,0x36
 out 0x77,al
%if RUN_MODE = 2
 mov al,9
 mov word [es:52],9
%else
 xor al,al
%endif
 out 0x71,al
 xor al,al
 out 0x71,al
 mov al,0x0a
 out 0,al
 mov word [es:12],4
 in al,0
 mov [es:46],al
 mov word [es:12],5
 in al,0
 mov [es:28],al
 mov al,0xfe
 out 2,al
 sti
 nop
wait_irq:
 cmp word [es:30],0
 je wait_irq
 cli
 mov ax,[es:30]
 mov [es:48],ax
 mov al,0x30
 out 0x77,al
%if RUN_MODE = 2
 mov al,40
 mov word [es:54],40
%else
 xor al,al
%endif
 out 0x71,al
 xor al,al
 out 0x71,al
 mov word [es:36],0x1111
 mov word [es:44],wake
 mov word [es:12],6
 sti
 hlt
wake:
 cli
 mov word [es:38],0x2222
 in al,2
 mov [es:50],al
 xor bx,bx
 xor si,si
 mov cx,62
checksum:
 add bx,[es:si]
 add si,2
 loop checksum
 mov [es:124],bx
 mov word [es:126],2
halt:
 hlt
 jmp halt
readword:
 in al,0x71
 mov ah,al
 in al,0x71
 xchg ah,al
 ret
handler:
 push ax
 push bp
 mov bp,sp
 inc word [es:30]
 mov ax,[ss:bp+4]
 mov [es:42],ax
 mov al,0x0b
 out 0,al
 in al,0
 mov [es:32],al
 mov al,0x20
 out 0,al
 in al,0
 mov [es:34],al
 pop bp
 pop ax
 iret
times 1022-($-$$) db 0
dw 0xaa55
