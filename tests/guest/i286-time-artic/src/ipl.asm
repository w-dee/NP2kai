; SPDX-License-Identifier: BSD-2-Clause
; Original single-sector DOS-free ARTIC word-read fixture.
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
 mov sp,0x1000
 mov ax,0x2900
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,272
 rep stosw
 mov ds,ax
 mov al,[0x045b]
 mov [es:14],ax                  ; capability evidence only
 push cs
 pop ds
 mov word [es:0],0x5241
 mov word [es:2],0x4354
 mov word [es:4],1
 mov word [es:6],544
 mov word [es:8],RUN_MODE
 mov word [es:10],20
 mov word [es:12],1              ; SYNTHETIC_EMULATOR_ARTIC_MODEL
 mov word [es:538],0xa55a
 mov si,schedule
 mov di,32
 mov bp,1
next:
 mov ax,[si]
 mov [es:di],ax                 ; case id
 mov [es:di+2],bp               ; fake sample identity
 mov dx,[si+2]
 mov [es:di+4],dx
 mov ax,[si+4]
 mov [es:di+8],ax               ; independent expected slice
 xor bx,bx
 mov cx,8192
work:
 inc bx
 loop work
 mov [es:di+10],bx              ; guest CPU progress witness
 cmp bp,19
 jne read_port
 xor al,al
 out 0x5f,al                    ; must not advance frozen fake phase
read_port:
 in ax,dx                       ; actual aligned word observation
 mov [es:di+6],ax
%if RUN_MODE = 2
 cmp ax,[es:di+8]
 jne failed
 mov word [es:di+12],1
 jmp advance
failed:
 inc word [es:16]
%else
 mov word [es:di+12],2           ; legacy observation, not hardware PASS
%endif
advance:
 add si,6
 add di,24
 inc bp
 cmp bp,21
 jne next
 xor bx,bx
 xor si,si
 mov cx,270
checksum:
 add bx,[es:si]
 add si,2
 loop checksum
 mov [es:540],bx
 mov ax,2
 cmp word [es:16],0
 je publish
 inc ax
publish:
 mov [es:542],ax                ; terminal state is written last
halt:
 hlt
 jmp halt
schedule:
%include "samples.inc"
 times 1022-($-$$) db 0
 dw 0xaa55
