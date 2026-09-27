; SPDX-License-Identifier: MIT AND BSD-2-Clause
; N3 direct uPD765A READ DATA / PC-98 DMA2 fixture.
; The CRC32 routine derives from the BSD2 N1/np2kbdtest routine.
bits 16
cpu 286
org 0
%define RESULT_SEG 0x2900
%define DMA_SEG 0x4000

    db 'ST2V'
    dw 1
    dw image_end-$$
entry:
    cli
    cld
    mov ax,0x2800
    mov ss,ax
    mov sp,0x1000
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
    mov ax,0xe1
    mov cx,2000
    rep stosw
    mov ax,RESULT_SEG
    mov es,ax
    xor di,di
    xor ax,ax
    mov cx,128
    rep stosw
    mov word [es:0],0x334e
    mov word [es:2],0x4446 ; N3FD result, unlike sector header size/version
    mov word [es:4],1
    mov word [es:6],256
    mov word [es:8],2
    mov word [es:18],96
    mov byte [es:252],1
    mov al,0xff
    out 0x02,al
    out 0x0a,al
    xor ax,ax
    mov es,ax
    mov word [es:0x4c],irq11
    mov ax,cs
    mov word [es:0x4e],ax
    mov ax,RESULT_SEG
    mov es,ax
    ; 2HD at 90/92/94, DMA2, IRQ11. Reset without reset IRQ (bit3=0),
    ; then select DMA operation and motor. No asserted spin-up time.
    mov al,3
    out 0xbe,al
    mov al,0x80
    out 0x94,al
    mov al,0x18
    out 0x94,al
    mov al,0x20
    out 0x08,al
    out 0x00,al
    mov al,0x7f
    out 0x02,al
    mov al,0xf7
    out 0x0a,al
    ; SPECIFY: DMA mode (ND=0). Timing fields are setup, not timing verdicts.
    mov si,specify
    mov cx,3
    call send_bytes
    jc setup_fail
    ; SENSE DRIVE STATUS, drive0/head0. Loader already left cylinder0.
    mov si,sense_drive
    mov cx,2
    call send_bytes
    jc setup_fail
    call recv_byte
    jc setup_fail
    mov [drive_status],al
    mov byte [setup_ok],1
setup_fail:
    mov bx,32
    mov byte [sector],7
    mov word [buffer],0x100
    mov word [expected],expected7
    call transaction
    mov bx,128
    mov byte [sector],8
    mov word [buffer],0x900
    mov word [expected],expected8
    call transaction
    mov ax,RESULT_SEG
    mov es,ax
    xor si,si
    mov cx,248
    call crc32
    mov [es:248],ax
    mov [es:250],dx
    mov si,fail_text
    mov al,3
    cmp word [es:14],0
    jne display
    mov si,pass_text
    mov al,2
 display:
    mov [es:252],al ; Publish exactly one terminal value after the CRC.
    mov ax,0xa000
    mov es,ax
    mov di,2*(2*80+4)
.print:
    lodsb
    test al,al
    jz idle
    mov [es:di],al
    add di,2
    jmp .print
idle:
    cli
    hlt
    jmp idle

transaction:
    cli
    mov [record],bx
    mov ax,RESULT_SEG
    mov es,ax
    mov al,[sector]
    sub al,6
    mov [es:bx],al
    mov byte [es:bx+1],2
    mov byte [es:bx+2],2
    mov byte [es:bx+3],1
    mov al,[sector]
    mov [es:bx+6],al
    mov byte [es:bx+7],3
    mov word [es:bx+8],1024
    mov byte [es:bx+31],0x46
    mov byte [es:bx+64],4
    mov ax,[buffer]
    mov [es:bx+52],ax
    mov al,[drive_status]
    mov [es:bx+58],al
    cmp byte [setup_ok],1
    jne .failed
    ; Expected CRC is independently computed from the embedded expected bytes.
    push es
    push cs
    pop es
    mov si,[expected]
    mov cx,1024
    call crc32
    pop es
    mov [es:bx+40],ax
    mov [es:bx+42],dx
    ; Poison is the per-byte complement: none can accidentally equal target.
    push es
    mov ax,DMA_SEG
    mov es,ax
    mov di,[buffer]
    mov byte [es:di-1],0x5c
    mov byte [es:di+1024],0xc5
    mov si,[expected]
    mov cx,1024
.poison:
    lodsb
    not al
    stosb
    loop .poison
    pop es
    ; Mask DMA2, clear byte flip-flop, program address/page/count/mode.
    mov al,6
    out 0x15,al
    xor al,al
    out 0x19,al
    mov ax,[buffer]
    out 0x09,al
    mov al,ah
    out 0x09,al
    mov al,4
    out 0x23,al
    mov ax,1023
    out 0x0b,al
    mov al,ah
    out 0x0b,al
    mov al,0x46
    out 0x17,al
    in al,0x11
    mov [es:bx+67],al
    call dma_snapshot
    mov [es:bx+10],ax
    mov [es:bx+12],dx
    mov al,0x0a
    out 0x08,al
    in al,0x08
    mov [es:bx+20],al
    mov al,[irq_count]
    mov [es:bx+22],al
    in al,0x90
    mov [es:bx+28],al
    mov byte [es:bx+3],2
    mov byte [phase],2
    mov al,2
    out 0x15,al
    mov al,[sector]
    mov [read_command+4],al
    mov si,read_command
    mov cx,9
    call send_bytes
    jc .failed
    mov byte [es:bx+59],9
    ; CPU polling supplies legacy DMA service opportunities. IF stays clear.
    mov bp,16
.tc_outer:
    mov cx,0xffff
.tc_poll:
    in al,0x11
    test al,4
    jnz .tc
    ; Detect publication while waiting for TC. Snapshot before acceptance;
    ; a request observed with incomplete DMA is a recorded failure.
    mov al,0x0a
    out 0x08,al
    in al,0x08
    test al,8
    jnz .early_irq
    loop .tc_poll
    dec bp
    jnz .tc_outer
    jmp .failed
.early_irq:
    mov [es:bx+68],al
    call dma_snapshot
    mov [es:bx+70],ax
    mov [es:bx+72],dx
    in al,0x11
    test al,4
    jnz .tc
    jmp .failed
.tc:
    mov [es:bx+18],al
    in al,0x11
    mov [es:bx+19],al
    call dma_snapshot
    mov [es:bx+14],ax
    mov [es:bx+16],dx
    mov bp,16
.irq_outer:
    mov cx,0xffff
.irq_poll:
    mov al,0x0a
    out 0x08,al
    in al,0x08
    test al,8
    jnz .pending
    loop .irq_poll
    dec bp
    jnz .irq_outer
    jmp .failed
.pending:
    mov [es:bx+21],al
    in al,0x90
    mov [es:bx+29],al
    ; Validate data BEFORE allowing IRQ acceptance, preserving causal order.
    push es
    mov ax,DMA_SEG
    mov es,ax
    mov si,[expected]
    mov di,[buffer]
    mov cx,1024
    xor dx,dx
    mov bp,0xffff
.compare:
    mov al,[es:di]
    cmp al,[si]
    je .equal
    cmp bp,0xffff
    jne .check_poison
    mov bp,di
    sub bp,[buffer]
.check_poison:
    not al
    cmp al,[si]
    jne .equal
    inc dx
.equal:
    inc si
    inc di
    loop .compare
    mov di,[buffer]
    mov al,[es:di-1]
    mov ah,[es:di+1024]
    pop es
    mov [es:bx+48],bp
    mov [es:bx+50],dx
    mov [es:bx+65],al
    mov [es:bx+66],ah
    push es
    mov ax,DMA_SEG
    mov es,ax
    mov si,[buffer]
    mov cx,1024
    call crc32
    pop es
    mov [es:bx+44],ax
    mov [es:bx+46],dx
    mov byte [es:bx+3],3
    mov byte [phase],3
    sti
    nop
    cli
    mov al,[irq_count]
    mov [es:bx+23],al
    ; Consume only seven result bytes AFTER TC and interrupt acceptance.
    mov di,bx
    add di,32
    mov cx,7
.results:
    call recv_byte
    jc .failed
    stosb
    loop .results
    in al,0x90
    mov [es:bx+30],al
    mov byte [phase],4
    mov byte [es:bx+3],4
    call validate
    jc .failed
    mov byte [es:bx+2],1
    inc word [es:12]
    jmp .done
.failed:
    mov byte [es:bx+2],2
    inc word [es:14]
    cmp word [es:16],0
    jne .done
    xor ax,ax
    mov al,[es:bx]
    mov [es:16],ax
.done:
    inc word [es:10]
    mov al,6
    out 0x15,al
    ret

validate:
    test byte [es:bx+58],0x20
    jz .bad
    cmp byte [es:bx+59],9
    jne .bad
    mov ax,[buffer]
    cmp [es:bx+10],ax
    jne .bad
    add ax,1024
    cmp [es:bx+14],ax
    jne .bad
    cmp [es:bx+54],ax
    jne .bad
    cmp word [es:bx+12],1023
    jne .bad
    cmp word [es:bx+16],0xffff
    jne .bad
    cmp word [es:bx+56],0xffff
    jne .bad
    test byte [es:bx+68],8
    jz .no_early_irq
    mov ax,[es:bx+70]
    cmp ax,[es:bx+14]
    jne .bad
    cmp word [es:bx+72],0xffff
    jne .bad
.no_early_irq:
    test byte [es:bx+67],4
    jnz .bad
    test byte [es:bx+18],4
    jz .bad
    test byte [es:bx+19],4
    jnz .bad
    test byte [es:bx+20],8
    jnz .bad
    test byte [es:bx+21],8
    jz .bad
    mov al,[es:bx+22]
    inc al
    cmp al,[es:bx+23]
    jne .bad
    test byte [es:bx+24],8
    jz .bad
    test byte [es:bx+25],0x80
    jz .bad
    test byte [es:bx+26],8
    jnz .bad
    test byte [es:bx+27],0x80
    jnz .bad
    cmp byte [es:bx+39],3
    jne .bad
    mov al,[es:bx+28]
    and al,0xc0
    cmp al,0x80
    jne .bad
    mov al,[es:bx+29]
    and al,0xf0
    cmp al,0xd0
    jne .bad
    cmp byte [es:bx+30],0x80
    jne .bad
    cmp word [es:bx+32],0
    jne .bad
    cmp word [es:bx+34],0
    jne .bad
    cmp word [es:bx+36],0x0100 ; legacy result H=0,R=1 after TC
    jne .bad
    cmp byte [es:bx+38],3
    jne .bad
    mov ax,[es:bx+40]
    cmp ax,[es:bx+44]
    jne .bad
    mov ax,[es:bx+42]
    cmp ax,[es:bx+46]
    jne .bad
    cmp word [es:bx+48],0xffff
    jne .bad
    cmp word [es:bx+50],0
    jne .bad
    cmp word [es:bx+65],0xc55c
    jne .bad
    clc
    ret
.bad:
    stc
    ret

; Returns AX=current address, DX=current count; preserves record BX and CX.
dma_snapshot:
    xor al,al
    out 0x19,al
    in al,0x09
    mov ah,al
    in al,0x09
    xchg al,ah
    push ax
    in al,0x0b
    mov ah,al
    in al,0x0b
    xchg al,ah
    mov dx,ax
    pop ax
    ret
send_bytes:
    push dx
.next:
    lodsb
    mov dl,al
    push cx
    mov cx,0xffff
.wait:
    in al,0x90
    and al,0xc0
    cmp al,0x80
    je .ready
    loop .wait
    pop cx
    pop dx
    stc
    ret
.ready:
    mov al,dl
    out 0x92,al
    pop cx
    loop .next
    pop dx
    clc
    ret
recv_byte:
    push cx
    mov cx,0xffff
.wait:
    in al,0x90
    and al,0xc0
    cmp al,0xc0
    je .ready
    loop .wait
    pop cx
    stc
    ret
.ready:
    in al,0x92
    pop cx
    clc
    ret
irq11:
    push ax
    push bx
    push dx
    push es
    mov ax,RESULT_SEG
    mov es,ax
    mov bx,[cs:record]
    inc byte [cs:irq_count]
    mov al,[cs:phase]
    mov [es:bx+39],al
    mov al,0x0b
    out 0x08,al
    out 0x00,al
    in al,0x08
    mov [es:bx+24],al
    in al,0x00
    mov [es:bx+25],al
    call dma_snapshot
    mov [es:bx+54],ax
    mov [es:bx+56],dx
    mov al,0x20
    out 0x08,al
    out 0x00,al
    in al,0x08
    mov [es:bx+26],al
    in al,0x00
    mov [es:bx+27],al
    pop es
    pop dx
    pop bx
    pop ax
    iret

; BSD-2-Clause: adapted np2kbdtest/N1 CRC32; ES:SI input, CX bytes,
; returns DX:AX; preserves BX/BP/SI/CX for the enclosing result record.
crc32:
    push bx
    push bp
    push si
    push cx
    mov ax,0xffff
    mov dx,0xffff
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
    pop cx
    pop si
    pop bp
    pop bx
    ret

specify db 3,0xdf,2
sense_drive db 4,0
read_command db 0x46,0,0,0,7,3,8,0x1b,0xff
setup_ok db 0
drive_status db 0
sector db 7
buffer dw 0x100
expected dw expected7
record dw 32
irq_count db 0
phase db 0
pass_text db 'N3 DIRECT FDC/DMA PASS 2/2',0
fail_text db 'N3 DIRECT FDC/DMA FAIL - inspect result',0
expected7: incbin 'sector7.bin'
expected8: incbin 'sector8.bin'
image_end:
