# SPDX-License-Identifier: MIT
"""Compatibility-only result schema; expected values are parent-profile facts."""
import struct
def verify_result(data,mode,profile):
    if len(data)!=128 or data[:4]!=b'PIPC':raise ValueError('magic/size')
    w=struct.unpack('<64H',data)
    assert w[2:6]==(1,128,mode,profile)
    assert w[61]==0xa55a and w[63]==2 and sum(w[:62])&65535==w[62]
    assert w[6]==6 and w[7]==0 and w[8:10]==(0x30,100)
    assert w[11]==0 and not any(w[28:61]), 'reserved fields'
    assert w[20]==8192 and w[18:20]==(0x1111,0x2222)
    assert w[21]==w[22], 'handler saved IP must be after HLT'
    if mode==2:
        assert (w[10],w[12],w[13])==(100,100,75), 'frozen/current/latched count'
        assert w[23]&1 and w[14]&1, 'expiry and count9 +2 PIT clocks retain IRR0'
        assert w[15]==2 and w[24]==1, 'one accepted IRQ per controlled event'
        assert w[16]&1 and not w[17]&1, 'ISR entry and EOI'
        assert w[25:28]==(254,9,40)
    return dict(state='PASS' if mode==2 else 'LEGACY_COMPATIBILITY_PROFILE_CAPTURED',
                authority='LEGACY_COMPATIBILITY_ASSERTION',profile=profile,mode=mode,
                current=w[10],frozen=w[12],latched=w[13],irr_at_two_ticks=w[14],
                accepted=w[15],isr_entry=w[16],isr_after_eoi=w[17],
                progress=w[20],saved_ip=w[21],wake_ip=w[22],
                nonclaims=['physical VM/VX timer/PIC equivalence','Linux realtime semantics','audio'])
