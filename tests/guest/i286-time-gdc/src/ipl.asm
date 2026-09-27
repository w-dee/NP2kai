; SPDX-License-Identifier: BSD-2-Clause
; Original N4 PC-98 floppy bootstrap. BIOS disk use ends before stage2.
bits 16
cpu 286
org 0
 cli
 cld
 jmp load
 times 510-($-$$) db 0
 dw 0xaa55
load:
 xor ax,ax
 mov ds,ax
 mov ax,0x2800
 mov ss,ax
 mov sp,0x1000
 mov al,[0x584]
 mov [cs:drive],al
 and al,0xfc
 cmp al,0x90
 jne failed
 mov ax,0x2000
 mov es,ax
 xor bp,bp
 mov si,STAGE_SECTORS
.next:
 mov al,[cs:drive]
 mov ah,0x56
 mov bx,1024
 mov ch,3
 mov cl,[cs:cyl]
 mov dh,[cs:head]
 mov dl,[cs:sector]
 push si
 push bp
 int 0x1b
 pop bp
 pop si
 jc failed
 test ah,ah
 jnz failed
 add bp,1024
 inc byte [cs:sector]
 cmp byte [cs:sector],9
 jb .advance
 mov byte [cs:sector],1
 xor byte [cs:head],1
 jnz .advance
 inc byte [cs:cyl]
.advance:
 dec si
 jnz .next
 cmp word [es:0],0x344e
 jne failed
 cmp word [es:2],0x5453
 jne failed
 cmp word [es:4],1
 jne failed
 cmp word [es:6],STAGE_BYTES
 jne failed
 jmp 0x2000:8
failed:
 mov ax,0x3000
 mov es,ax
 mov word [es:4094],4
 cli
 hlt
 jmp failed
drive db 0
cyl db 0
head db 0
sector db 2
 times 1022-($-$$) db 0
 dw 0xaa55
