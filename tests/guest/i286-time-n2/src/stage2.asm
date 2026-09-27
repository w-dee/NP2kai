; SPDX-License-Identifier: MIT AND BSD-2-Clause
; N2: one long REP MOVSB, PIT IRQ capture, restart and exact completion.
; CRC32 routine below is BSD-2-Clause, see the adjacent notice.
bits 16
cpu 286
org 0
%define RESULT_SEG 0x2900
%define SRC_SEG 0x3000
%define DST_SEG 0x4000
%define START_OFF 0x0100
%define COPY_COUNT 0x8000
%define END_OFF (START_OFF + COPY_COUNT)
%define PIT_RELOAD 0x1000
%define R1 32
%define R2 64
%define R3 96

    db 'ST2V'
    dw 1
    dw image_end - $$
entry:
    cli
    cld
    mov ax,0x2800
    mov ss,ax
    mov sp,0x1000
    push cs
    pop ds
    ; Screen setup occurs before the timing stimulus.
    mov ax,0x0a00
    int 0x18
    mov ah,0x0c
    int 0x18
    push cs
    pop ds
    mov ax,0xa000
    mov es,ax
    xor di,di
    mov ax,0x20
    mov cx,2000
    rep stosw
    mov ax,0xa200
    mov es,ax
    xor di,di
    mov ax,0x00e1
    mov cx,2000
    rep stosw
    push cs
    pop ds
    mov si,title
    mov di,2*(2*80+4)
    call print_string

    ; Install IRQ0 and suppress IRQs while all memory is initialized.
    xor ax,ax
    mov es,ax
    mov word [es:0x20],irq0
    mov ax,cs
    mov word [es:0x22],ax
    mov al,0xff
    out 0x02,al
    mov al,0x20
    out 0x00,al

    ; Source pattern is affine modulo 256, generated without imported data.
    mov ax,SRC_SEG
    mov es,ax
    mov di,START_OFF
    mov cx,COPY_COUNT
    mov al,0x13
.fill_source:
    stosb
    add al,0x3d
    loop .fill_source
    mov ax,DST_SEG
    mov es,ax
    mov di,START_OFF
    mov cx,COPY_COUNT
    mov al,0xa5
    rep stosb
    mov byte [es:START_OFF-1],0x5c
    mov byte [es:END_OFF],0xc5

    ; Independent source checksum before the observed REP begins.
    mov ax,SRC_SEG
    mov ds,ax
    mov si,START_OFF
    mov cx,COPY_COUNT
    xor bx,bx
    xor ah,ah
.source_sum:
    lodsb
    add bx,ax
    loop .source_sum
    mov [cs:source_sum],bx

    ; PIT channel 0 one-shot, IRQ0 only. Initial IRR must be clear.
    mov al,0xfe
    out 0x02,al
    mov ax,PIT_RELOAD
    call arm_pit
    call read_irr
    mov [cs:pre_irr],al
    mov ax,SRC_SEG
    mov ds,ax
    mov ax,DST_SEG
    mov es,ax
    mov si,START_OFF
    mov di,START_OFF
    mov cx,COPY_COUNT
    mov byte [cs:phase],1
    sti
rep_start:
    rep movsb
rep_done:
    mov byte [cs:phase],2
    cli
    mov [cs:final_cx],cx
    mov [cs:final_si],si
    mov [cs:final_di],di

    ; Independent byte-by-byte comparison, plus a destination checksum.
    mov si,START_OFF
    mov di,START_OFF
    mov cx,COPY_COUNT
    xor bx,bx
    xor ah,ah
    mov dx,0xffff
.compare:
    mov al,[es:di]
    add bx,ax
    cmp al,[si]
    je .equal
    cmp dx,0xffff
    jne .equal
    mov dx,si
    sub dx,START_OFF
.equal:
    inc si
    inc di
    loop .compare
    mov [cs:dest_sum],bx
    mov [cs:first_mismatch],dx
    mov al,[es:START_OFF-1]
    mov [cs:before_canary],al
    mov al,[es:END_OFF]
    mov [cs:after_canary],al
    push cs
    pop ds
    mov ax,RESULT_SEG
    mov es,ax
    xor di,di
    xor ax,ax
    mov cx,128
    rep stosw
    mov word [es:0],0x324e  ; N2RP
    mov word [es:2],0x5052
    mov word [es:4],1
    mov word [es:6],256
    mov word [es:8],3
    mov word [es:18],32
    mov byte [es:252],1
    mov byte [es:R1],1
    mov byte [es:R2],2
    mov byte [es:R3],3
    mov byte [es:R1+1],2   ; backend/device regression
    mov byte [es:R2+1],1   ; architectural CPU assertion
    mov byte [es:R3+1],1   ; architectural CPU assertion

    ; ID1: source programming, PIC service, CPU acceptance before completion.
    mov word [es:R1+4],PIT_RELOAD
    xor ah,ah
    mov al,[pre_irr]
    mov [es:R1+6],ax
    mov ax,[irq_count]
    mov [es:R1+8],ax
    xor ah,ah
    mov al,[first_isr_entry]
    mov [es:R1+10],ax
    mov al,[first_isr_after]
    mov [es:R1+12],ax
    mov al,[first_phase]
    mov [es:R1+14],ax
    mov al,[phase]
    mov [es:R1+16],ax
    mov bx,R1
    cmp byte [pre_irr],0
    jne .bad1
    cmp word [irq_count],1
    jne .bad1
    test byte [first_isr_entry],1
    jz .bad1
    test byte [first_isr_after],1
    jnz .bad1
    cmp byte [first_phase],1
    jne .bad1
    cmp byte [phase],2
    jne .bad1
    call pass_case
    jmp .end1
.bad1:
    call fail_case
.end1:
    ; ID2: interrupted REP continuation state, including restart IP.
    mov word [es:R2+4],COPY_COUNT
    mov ax,[first_cx]
    mov [es:R2+6],ax
    mov ax,[first_si]
    mov [es:R2+8],ax
    mov ax,[first_di]
    mov [es:R2+10],ax
    mov ax,[first_ip]
    mov [es:R2+12],ax
    mov word [es:R2+14],rep_start
    mov ax,[first_flags]
    mov [es:R2+16],ax
    mov ax,[irq_count]
    mov [es:R2+18],ax
    mov word [es:R2+20],START_OFF
    mov word [es:R2+22],START_OFF
    mov bx,R2
    cmp word [first_cx],0
    je .bad2
    cmp word [first_cx],COPY_COUNT
    jae .bad2
    cmp word [first_ip],rep_start
    jne .bad2
    mov ax,COPY_COUNT
    sub ax,[first_cx]
    add ax,START_OFF
    cmp ax,[first_si]
    jne .bad2
    cmp ax,[first_di]
    jne .bad2
    test word [first_flags],0x0200  ; interrupted IF=1
    jz .bad2
    test word [first_flags],0x0400  ; DF=0
    jnz .bad2
    call pass_case
    jmp .end2
.bad2:
    call fail_case
.end2:
    ; ID3: resumed REP reaches exact state and exact memory image.
    mov ax,[final_cx]
    mov [es:R3+4],ax
    mov ax,[final_si]
    mov [es:R3+6],ax
    mov ax,[final_di]
    mov [es:R3+8],ax
    mov ax,[source_sum]
    mov [es:R3+10],ax
    mov ax,[dest_sum]
    mov [es:R3+12],ax
    mov ax,[first_mismatch]
    mov [es:R3+14],ax
    xor ah,ah
    mov al,[before_canary]
    mov [es:R3+16],ax
    mov al,[after_canary]
    mov [es:R3+18],ax
    mov ax,[irq_count]
    mov [es:R3+20],ax
    mov bx,R3
    cmp word [final_cx],0
    jne .bad3
    cmp word [final_si],END_OFF
    jne .bad3
    cmp word [final_di],END_OFF
    jne .bad3
    cmp word [first_mismatch],0xffff
    jne .bad3
    mov ax,[source_sum]
    cmp ax,0xc000       ; affine 32768-byte pattern checksum
    jne .bad3
    cmp ax,[dest_sum]
    jne .bad3
    cmp byte [before_canary],0x5c
    jne .bad3
    cmp byte [after_canary],0xc5
    jne .bad3
    call pass_case
    jmp .end3
.bad3:
    call fail_case
.end3:
    mov ax,RESULT_SEG
    mov es,ax
    mov cx,248
    mov di,248
    call crc32
    cmp word [es:14],0
    jne terminal_fail
    mov byte [es:252],2
    mov si,pass_text
    jmp show_result
terminal_fail:
    mov byte [es:252],3
    mov si,fail_text
show_result:
    mov ax,0xa000
    mov es,ax
    mov di,2*(4*80+4)
    call print_string
idle:
    cli
    hlt
    jmp idle

pass_case:
    mov byte [es:bx+2],1
    inc word [es:10]
    inc word [es:12]
    ret
fail_case:
    mov byte [es:bx+2],2
    inc word [es:10]
    inc word [es:14]
    cmp word [es:16],0
    jne .done
    xor ax,ax
    mov al,[es:bx]
    mov [es:16],ax
.done:
    ret
arm_pit:
    push dx
    push ax
    mov dx,0x77
    mov al,0x30
    out dx,al
    pop ax
    mov dx,0x71
    out dx,al
    mov al,ah
    out dx,al
    pop dx
    ret
read_irr:
    mov al,0x0a
    out 0x00,al
    in al,0x00
    ret
print_string:
    push ax
    push es
    mov ax,0xa000
    mov es,ax
.next:
    lodsb
    or al,al
    jz .done
    mov [es:di],al
    add di,2
    jmp .next
.done:
    pop es
    pop ax
    ret

irq0:
    push bp
    mov bp,sp
    push ax
    push dx
    push ds
    push es
    push cs
    pop ds
    inc word [irq_count]
    cmp word [irq_count],1
    jne .eoi
    mov [first_cx],cx
    mov [first_si],si
    mov [first_di],di
    mov ax,[ss:bp+2]
    mov [first_ip],ax
    mov ax,[ss:bp+6]
    mov [first_flags],ax
    mov al,[phase]
    mov [first_phase],al
    mov al,0x0b
    out 0x00,al
    in al,0x00
    mov [first_isr_entry],al
.eoi:
    mov al,0x20
    out 0x00,al
    cmp word [irq_count],1
    jne .done
    mov al,0x0b
    out 0x00,al
    in al,0x00
    mov [first_isr_after],al
.done:
    pop es
    pop ds
    pop dx
    pop ax
    pop bp
    iret

; CRC32/ISO-HDLC implementation from esp-np2kai np2kbdtest IPL.
; SPDX-License-Identifier: BSD-2-Clause
crc32:
    mov ax,0xffff
    mov dx,0xffff
    xor si,si
.byte:
    mov bl,[es:si]
    xor al,bl
    mov bp,8
.bit:
    test ax,1
    jz .shift
    shr dx,1
    rcr ax,1
    xor ax,0x8320
    xor dx,0xedb8
    jmp short .done
.shift:
    shr dx,1
    rcr ax,1
.done:
    dec bp
    jnz .bit
    inc si
    loop .byte
    not ax
    not dx
    mov [es:di],ax
    mov [es:di+2],dx
    ret

irq_count dw 0
pre_irr db 0
first_cx dw 0
first_si dw 0
first_di dw 0
first_ip dw 0
first_flags dw 0
first_phase db 0
first_isr_entry db 0
first_isr_after db 0
phase db 0
final_cx dw 0
final_si dw 0
final_di dw 0
source_sum dw 0
dest_sum dw 0
first_mismatch dw 0
before_canary db 0
after_canary db 0
title db 'N2 i286 LONG REP MOVSB IPL',0
pass_text db 'N2 PASS 3/3',0
fail_text db 'N2 FAIL - inspect structured result',0
image_end:
