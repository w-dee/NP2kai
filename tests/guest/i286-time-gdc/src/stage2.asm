; SPDX-License-Identifier: BSD-2-Clause
; Original N4 guest. All device operations below are actual guest IN/OUT.
bits 16
cpu 286
org 0
%include "n4.inc"
db 'N4ST'
dw 1, image_end-$$
entry:
 cli
 cld
 mov ax,0x2800
 mov ss,ax
 mov sp,0x1000
 push cs
 pop ds
 mov ax,0x3000
 mov es,ax
 xor di,di
 xor ax,ax
 mov cx,2048
 rep stosw
 mov word [es:0],0x344e
 mov word [es:2],0x4447
 mov word [es:4],1
 mov word [es:6],4096
 mov word [es:8],80
 mov word [es:12],RUN_MODE
 mov word [es:14],SCAN_CLASS
 mov si,build_id
 mov di,16
 mov cx,8
 rep movsb
 mov word [es:28],SCAN_CLASS
 mov word [es:40],0xc33c
 mov word [es:42],0x5aa5
 mov word [es:44],28
 mov word [es:4084],0xc33c
 mov word [es:4086],0x5aa5
 mov word [es:4094],1
 ; Retain BIOS PIC vector configuration (08h/10h); mask both controllers.
 mov al,0xff
 out 0x02,al
 out 0x0a,al
 push ds
 xor ax,ax
 mov ds,ax
 mov word [0x28],irq2
 mov word [0x2a],0x2000
 pop ds
 call program
 call settle
 mov cx,7
.first:
 push cx
 call sample
 pop cx
 loop .first
 xor dl,dl
 call wait_v
 call sample                       ; 8: legacy display observation
 mov dl,0x20
 call wait_v
 call sample                       ; 9: legacy VSync observation
 call sample                       ; 10
 xor dl,dl
 call wait_v
 call sample                       ; 11
 call frame
 call sample                       ; 12
 call settle
 call frame
 call sample                       ; 13
 call sample                       ; 14: huge jump requires host binding
 call sample                       ; 15: before CPU work
 mov cx,32768
.work:
 add word [es:32],1
 adc word [es:34],0
 loop .work
 call sample                       ; 16: after CPU work
 mov word [es:24],0x3010            ; future CPU-held service checkpoint
 call sample                       ; 17
 mov al,0xff
 out 0x02,al
 out 0x64,al                       ; arm masked CRT request
 mov word [es:24],0x3002
 mov dl,4
 call wait_irr
 call sample                       ; 18: pending, no acceptance
 xor dl,dl
 call wait_irr
 call sample                       ; 19: display start expires request
 mov al,0xfb
 out 0x02,al
 out 0x64,al
 mov word [es:24],0x3003
 sti
 mov cx,0xffff
.accept:
 cmp word [es:36],1
 je .accepted
 loop .accept
 mov word [es:38],3
.accepted:
 cli
 call sample                       ; 20: handler deliberately withheld EOI
 out 0x64,al
 mov word [es:24],0x3004
 call settle
 call sample                       ; 21: ISR across repeated frames
 call eoi
 call sample                       ; 22
 xor dl,dl
 call wait_irr
 mov word [hlt_entry],0x1111
 mov word [wake_ip],woke
 out 0x64,al
 mov word [es:24],0x3005
 sti
 hlt
woke:
 cli
 mov word [hlt_wake],0x2222
 call sample                       ; 23
 call eoi
 mov al,0xff
 out 0x02,al
 call sample                       ; 24
 mov al,0x47
 out 0xa2,al
 mov al,SLAVE_PITCH
 out 0xa0,al
 call sample                       ; 25: status read also drains FIFO
 call sample                       ; 26
 inc byte [master+4]
 mov word [es:28],SCAN_CLASS+100
 call program
 call settle
 call sample                       ; 27: reprogram, committed by host observation
 dec byte [master+4]
 mov word [es:28],SCAN_CLASS
 call program
 call settle
 call sample                       ; 28
 ; Standard reflected CRC32, entirely computed by the guest.
 xor si,si
 mov cx,4088
 mov ax,0xffff
 mov dx,ax
.crc_byte:
 xor al,[es:si]
 mov bl,8
.crc_bit:
 shr dx,1
 rcr ax,1
 jnc .no_poly
 xor dx,0xedb8
 xor ax,0x8320
.no_poly:
 dec bl
 jnz .crc_bit
 inc si
 loop .crc_byte
 not ax
 not dx
 mov [es:4088],ax
 mov [es:4090],dx
 mov ax,2
 cmp word [es:38],0
 je .terminal
 inc ax
.terminal:
 mov [es:4094],ax                  ; terminal publication is the final RAM write
.stop:
 hlt
 jmp .stop

program:
 mov dx,0x9a8
 mov al,CLASS_SELECTOR
 out dx,al
 mov al,0x0f
 out 0x62,al
 mov si,master
 mov cx,8
.m:
 lodsb
 out 0x60,al
 loop .m
 mov al,0x47
 out 0x62,al
 mov al,80
 out 0x60,al
 in al,0x60
 mov al,0x0f
 out 0xa2,al
 mov si,slave
 mov cx,8
.s:
 lodsb
 out 0xa0,al
 loop .s
 mov al,0x47
 out 0xa2,al
 mov al,SLAVE_PITCH
 out 0xa0,al
 in al,0xa0
 mov word [es:24],0x1001
 ret

; Bounded legacy polling. IN is followed by MOV, never the SEARCH_SYNC idiom.
; Experimental guest delegates each wait to a checkpoint, unchanged thereafter.
wait_v:
%if RUN_MODE = 2
 mov ax,0x1100
 or al,dl
 mov [es:24],ax
 ret
%else
 mov bx,8
.outer:
 mov cx,0xffff
.again:
 in al,0x60
 mov ah,al
 and ah,0x20
 inc word [polls]
 cmp ah,dl
 je .done
 loop .again
 dec bx
 jnz .outer
 mov word [es:38],1
.done:
 ret
%endif
frame:
 xor dl,dl
 call wait_v
 mov dl,0x20
 call wait_v
 xor dl,dl
 jmp wait_v
settle:
 call frame
 jmp frame
wait_irr:
%if RUN_MODE = 2
 mov ax,0x1200
 or al,dl
 mov [es:24],ax
 ret
%else
 mov bx,8
.outer:
 mov cx,0xffff
.again:
 mov al,0x0a
 out 0x00,al
 in al,0x00
 and al,4
 inc word [polls]
 cmp al,dl
 je .done
 loop .again
 dec bx
 jnz .outer
 mov word [es:38],2
.done:
 ret
%endif

eoi:
 mov al,0x62
 out 0x00,al
 inc word [eoi_count]
 mov al,0x0b
 out 0x00,al
 in al,0x00
 mov [after_eoi],al
 ret

irq2:
 push ax
 push bp
 mov bp,sp
 mov ax,[ss:bp+4]
 mov [cs:saved_ip],ax
 mov ax,[ss:bp+6]
 mov [cs:saved_cs],ax
 mov ax,[ss:bp+8]
 mov [cs:saved_flags],ax
 mov al,0x0b
 out 0x00,al
 in al,0x00
 mov [cs:handler_isr],al
 inc word [es:36]
 pop bp
 pop ax
 iret

sample:
 inc word [es:26]
 mov ax,[es:26]
 mov [es:10],ax
 dec ax
 mov bx,80
 mul bx
 mov di,ax
 add di,128
 mov ax,[es:26]
 mov [es:di],ax
 mov [es:di+2],ax
 mov byte [es:di+6],2
 mov byte [es:di+7],1
 cmp ax,15
 jb .category
 cmp ax,17
 ja .category
 mov byte [es:di+6],3
.category:
 cmp ax,14
 je .deferred
 cmp ax,17
 jne .observed
.deferred:
 mov byte [es:di+7],3
.observed:
 add ax,0x2000
 mov [es:di+10],ax
 mov [es:24],ax                    ; host may position future fake time here
 in al,0x60
 mov [es:di+12],al
 in al,0xa0
 mov [es:di+13],al
 mov word [es:di+14],0xffff
 mov al,[es:di+12]
 mov cl,5
 shr al,cl
 and al,1
 mov [es:di+16],al
 mov al,[es:di+12]
 mov cl,6
 shr al,cl
 and al,1
 mov [es:di+17],al
 mov al,[es:di+13]
 mov cl,5
 shr al,cl
 and al,1
 mov [es:di+18],al
 mov al,[es:di+13]
 mov cl,6
 shr al,cl
 and al,1
 mov [es:di+19],al
 mov al,0x0a
 out 0x00,al
 in al,0x00
 mov [es:di+20],al
 mov al,0x0b
 out 0x00,al
 in al,0x00
 mov [es:di+21],al
 in al,0x02
 mov [es:di+22],al
 mov al,[es:di+13]
 mov cl,3
 shr al,cl
 and al,1
 mov [es:di+23],al
 mov al,[es:di+12]
 and al,7
 mov [es:di+24],al
 mov al,[es:di+13]
 and al,7
 mov [es:di+25],al
 mov ax,[es:36]
 mov [es:di+26],ax
 mov ax,[hlt_entry]
 mov [es:di+28],ax
 mov ax,[hlt_wake]
 mov [es:di+30],ax
 mov ax,[es:32]
 mov [es:di+32],ax
 mov ax,[es:34]
 mov [es:di+34],ax
 mov al,[handler_isr]
 mov [es:di+36],al
 mov al,[after_eoi]
 mov [es:di+37],al
 mov ax,[saved_ip]
 mov [es:di+38],ax
 mov ax,[wake_ip]
 mov [es:di+40],ax
 mov ax,[saved_cs]
 mov [es:di+42],ax
 mov ax,[saved_flags]
 mov [es:di+44],ax
 mov ax,[polls]
 mov [es:di+46],ax
 mov ax,[es:28]
 mov [es:di+4],ax
 mov word [es:di+8],7
 push di
 add di,48
 mov si,master
 mov cx,16
 rep movsb
 pop di
 mov word [es:di+64],0x0f0f
 mov byte [es:di+66],CLASS_SELECTOR
 mov ax,[eoi_count]
 mov [es:di+68],ax
 mov word [es:di+72],0xc33c
 mov word [es:di+74],0x5aa5
 ret

hlt_entry dw 0
hlt_wake dw 0
saved_ip dw 0
wake_ip dw 0
saved_cs dw 0
saved_flags dw 0
handler_isr db 0
after_eoi db 0
eoi_count dw 0
polls dw 0
build_id: BUILD_ID
master: MASTER_SYNC
slave: SLAVE_SYNC
image_end:
