; SPDX-License-Identifier: BSD-2-Clause
; PC-9801-86 native OPNA A/B: actual IN/OUT, IF, HLT, ISR and EOI.
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
 mov word [0x50],handler
 mov [0x52],cs
 mov ax,0x2900
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,64
 rep stosw
 mov word [es:0],0x364e
 mov word [es:2],0x544f
 mov al,0xff
 out 2,al
 out 0x0a,al
 mov ax,0xff24
 call regwrite
 mov ax,0x0325
 call regwrite
 mov ax,0x0527
 call regwrite
 mov word [es:12],1
 call status
 mov [es:16],al
 mov cx,8192
 xor bx,bx
work:
 inc bx
 loop work
 mov [es:18],bx
 mov word [es:12],2
 call status
 mov [es:20],al
 mov word [es:12],3
 call status
 mov [es:22],al
 mov al,0x0a
 out 8,al
 in al,8
 mov [es:24],al
 mov ax,[es:30]
 mov [es:26],ax
 mov al,0xef
 out 0x0a,al
 mov al,0x7f
 out 2,al
 mov word [es:12],4
 mov cx,512
wait_if:
 loop wait_if
 mov ax,[es:30]
 mov [es:28],ax
 sti
 nop
wait_first:
 cmp word [es:30],1
 jne wait_first
 cli
 mov word [es:44],wake
 mov word [es:12],5
 sti
 hlt
wake:
 cli
 mov word [es:46],0x2222
 mov ax,[es:30]
 mov [es:48],ax
 mov word [es:126],2
halt:
 hlt
 jmp halt
status:
 mov dx,0x188
 in al,dx
 ret
regwrite:
 mov dx,0x188
 out dx,al
 add dx,2
 mov al,ah
 out dx,al
 ret
handler:
 push ax
 push dx
 inc word [es:30]
 mov al,0x0b
 out 8,al
 in al,8
 mov [es:32],al
 mov ax,0x1527
 call regwrite
 mov al,0x20
 out 8,al
 out 0,al
 in al,8
 mov [es:34],al
 pop dx
 pop ax
 iret
times 1022-($-$$) db 0
dw 0xaa55
