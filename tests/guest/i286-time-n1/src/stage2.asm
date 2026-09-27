; SPDX-License-Identifier: MIT AND BSD-2-Clause
; N1 standalone i286 PIT/PIC interrupt fixture. CRC32 routine is BSD-2-Clause.
bits 16
cpu 286
org 0
%define RSEG 0x2900
%define PIT_DATA 0x71
%define PIT_CTRL 0x77
%define PIC_CMD 0x00
%define PIC_MASK 0x02
%define COUNT 0x2000
%define R1 32
%define R2 56
%define R3 80
%define R4 104
%define R5 128
%define R6 152

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
    mov ax,0xa000
    mov es,ax
    mov si,title
    mov di,2*(2*80+4)
    call print_string
    mov ax,RSEG
    mov es,ax
    xor di,di
    xor ax,ax
    mov cx,128
    rep stosw
    mov word [es:0],0x314e  ; N1TM
    mov word [es:2],0x4d54
    mov word [es:4],1
    mov word [es:6],256
    mov word [es:8],6
    mov word [es:18],24
    mov byte [es:252],1
    mov byte [es:R1],1
    mov byte [es:R2],2
    mov byte [es:R3],3
    mov byte [es:R4],4
    mov byte [es:R5],5
    mov byte [es:R6],6
    mov byte [es:R1+1],2
    mov byte [es:R2+1],2
    mov byte [es:R3+1],2
    mov byte [es:R4+1],2
    mov byte [es:R5+1],1
    mov byte [es:R6+1],1
    ; Exclusive IRQ0 vector. No DOS, TSR, or resident software.
    xor ax,ax
    mov es,ax
    mov word [es:0x20],irq0
    mov ax,cs
    mov word [es:0x22],ax
    mov ax,RSEG
    mov es,ax
    mov al,0xff
    out PIC_MASK,al
    mov al,0x20
    out PIC_CMD,al
    mov al,0x0a
    out PIC_CMD,al

    ; 1: PIT mode 0 count, live reads, latched reads, relational progress.
    mov bx,R1
    mov ax,COUNT
    call arm_pit
    call read_count
    mov [es:bx+4],ax
    call latch_count
    mov [es:bx+6],ax
    mov cx,400
.delay1:
    loop .delay1
    call latch_count
    mov [es:bx+8],ax
    cmp word [es:bx+4],0
    je .bad1
    cmp word [es:bx+4],COUNT
    ja .bad1
    mov ax,[es:bx+4]
    cmp ax,[es:bx+6]
    jb .bad1
    cmp word [es:bx+6],0
    je .bad1
    cmp word [es:bx+8],0
    je .bad1
    mov ax,[es:bx+8]
    cmp ax,[es:bx+6]
    jae .bad1
    call pass_case
    jmp .end1
.bad1:
    call fail_case
.end1:
    ; 2: mask blocks CPU acceptance. IRR is observed, never treated as
    ; persistent physical edge/level truth.
    mov bx,R2
    mov byte [es:bx+23],0xff
    mov ax,COUNT
    call arm_pit
    call wait_irr
    mov [es:bx+20],al
    test al,1
    jz .bad2
    mov ax,[handler_count]
    mov [es:bx+8],ax
    cmp ax,0
    jne .bad2
    call pass_case
    jmp .end2
.bad2:
    call fail_case
.end2:
    ; Allow the legacy mask-event clearing interval to elapse before rearm.
    mov cx,0xffff
.drain:
    loop .drain
    mov al,0xfe
    out PIC_MASK,al

    ; 3: request while IF=0, accept after STI, ISR then EOI, second service.
    mov bx,R3
    mov byte [es:bx+23],0xfe
    mov ax,COUNT
    call arm_pit
    call wait_irr
    mov [es:bx+20],al
    test al,1
    jz .bad3
    mov byte [phase],3
    sti
    nop
.after3:
    cli
    mov ax,[handler_count]
    mov [es:bx+8],ax
    call copy_irq
    cmp ax,1
    jne .bad3
    cmp byte [es:bx+21],1
    jne .bad3
    test byte [es:bx+22],1
    jnz .bad3
    call pass_case
    jmp .end3
.bad3:
    call fail_case
.end3:

    ; 4: STI; HLT must sleep and resume at the instruction after HLT.
    mov bx,R4
    mov byte [es:bx+23],0xfe
    mov ax,COUNT
    call arm_pit
    call read_irr
    mov [es:bx+20],al
    test al,1
    jnz .bad4
    mov byte [phase],4
    mov word [marker],0x4411
    sti
    hlt
.after4:
    mov word [marker],0x4422
    cli
    mov ax,[handler_count]
    mov [es:bx+8],ax
    call copy_irq
    mov dx,[marker]
    mov [es:bx+10],dx
    cmp ax,2
    jne .bad4
    cmp word [es:bx+14],.after4
    jne .bad4
    cmp word [irq_marker],0x4411
    jne .bad4
    cmp word [marker],0x4422
    jne .bad4
    call pass_case
    jmp .end4
.bad4:
    call fail_case
.end4:

    ; 5: pre-pend IRQ with IF=0. STI must allow one following instruction.
    mov bx,R5
    mov byte [es:bx+23],0xfe
    mov ax,COUNT
    call arm_pit
    call wait_irr
    mov [es:bx+20],al
    test al,1
    jz .bad5
    mov byte [phase],5
    mov word [marker],0x5511
    sti
    mov word [marker],0x5522
.after5:
    cli
    mov ax,[handler_count]
    mov [es:bx+8],ax
    call copy_irq
    cmp ax,3
    jne .bad5
    cmp word [es:bx+14],.after5
    jne .bad5
    cmp word [irq_marker],0x5522
    jne .bad5
    call pass_case
    jmp .end5
.bad5:
    call fail_case
.end5:

    ; 6: pending IRQ; STI permits MOV SS; MOV SS inhibits through MOV SP.
    mov bx,R6
    mov byte [es:bx+23],0xfe
    mov ax,COUNT
    call arm_pit
    call wait_irr
    mov [es:bx+20],al
    test al,1
    jz .bad6
    mov byte [phase],6
    mov ax,0x2800
    sti
    mov ss,ax
    mov sp,0x1800
.after6:
    cli
    mov ax,[handler_count]
    mov [es:bx+8],ax
    call copy_irq
    cmp ax,4
    jne .bad6
    cmp word [es:bx+14],.after6
    jne .bad6
    cmp word [es:bx+18],0x17f8
    jne .bad6
    call pass_case
    jmp .end6
.bad6:
    call fail_case
.end6:
    mov sp,0x1000

    ; CRC covers bytes 0..247, terminal state is published last.
    mov ax,RSEG
    mov es,ax
    mov cx,248
    mov di,248
    call crc32
    cmp word [es:14],0
    jne terminal_fail
    mov byte [es:252],2
    mov si,passed_text
    jmp display_result
terminal_fail:
    mov byte [es:252],3
    mov si,failed_text
display_result:
    mov ax,0xa000
    mov es,ax
    mov di,2*(4*80+4)
    call print_string
idle:
    cli
    hlt
    jmp idle

; BX is current record, ES is result segment. Preserve BX in all helpers.
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
copy_irq:
    mov dx,[irq_ip]
    mov [es:bx+14],dx
    mov dx,[irq_sp]
    mov [es:bx+18],dx
    mov dx,[irq_marker]
    mov [es:bx+16],dx
    mov dl,[irq_isr_entry]
    mov [es:bx+21],dl
    mov dl,[irq_isr_after]
    mov [es:bx+22],dl
    mov dl,[phase]
    mov [es:bx+3],dl
    ret
arm_pit:
    ; AX=count; one-shot mode 0, low/high bytes.
    push dx
    push ax
    mov dx,PIT_CTRL
    mov al,0x30
    out dx,al
    pop ax
    mov dx,PIT_DATA
    out dx,al
    mov al,ah
    out dx,al
    pop dx
    ret
read_count:
    push dx
    mov dx,PIT_DATA
    in al,dx
    mov ah,al
    in al,dx
    xchg al,ah
    pop dx
    ret
latch_count:
    push dx
    mov dx,PIT_CTRL
    xor al,al
    out dx,al
    pop dx
    call read_count
    ret
read_irr:
    mov al,0x0a
    out PIC_CMD,al
    in al,PIC_CMD
    ret
wait_irr:
    push cx
    mov cx,0xffff
.loop:
    call read_irr
    test al,1
    jnz .found
    loop .loop
.found:
    pop cx
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
    inc word [handler_count]
    mov ax,[ss:bp+2]
    mov [irq_ip],ax
    mov [irq_sp],bp
    mov ax,[marker]
    mov [irq_marker],ax
    mov al,0x0b
    out PIC_CMD,al
    in al,PIC_CMD
    mov [irq_isr_entry],al
    mov al,0x20
    out PIC_CMD,al
    mov al,0x0b
    out PIC_CMD,al
    in al,PIC_CMD
    mov [irq_isr_after],al
    pop es
    pop ds
    pop dx
    pop ax
    pop bp
    iret

; CRC32/ISO-HDLC implementation reused from esp-np2kai np2kbdtest IPL.
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

handler_count dw 0
irq_ip dw 0
irq_sp dw 0
irq_marker dw 0
irq_isr_entry db 0
irq_isr_after db 0
phase db 0
marker dw 0
title db 'N1 i286 PIT/PIC/INTERRUPT IPL',0
passed_text db 'N1 PASS 6/6',0
failed_text db 'N1 FAIL - inspect structured result',0
image_end:
