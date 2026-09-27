# SPDX-License-Identifier: MIT
"""N4 v1 wire format and bounded assertions. No product clock authority."""
import struct
import zlib

PARENT = '134af751728c0a2f85abcf29e45a93ebfb94b21b'
ADDRESS = 0x30000
SIZE = 4096
HEADER = 128
RECORD = 80
CRC_OFFSET = 4088
TERMINAL_OFFSET = 4094
MODES = {1: 'LEGACY_GDC_OBSERVATION', 2: 'MACHINE_TIME_GDC_EXPERIMENTAL'}
CATEGORIES = {1: 'INTEGRATION_ASSERTION', 2: 'LEGACY_COMPATIBILITY_ASSERTION',
              3: 'ARCHITECTURAL_ASSERTION', 4: 'DEVICE_RELATIONAL_ASSERTION',
              5: 'HARDWARE_QUALIFIED_ASSERTION', 6: 'INCONCLUSIVE_NEEDS_HARDWARE_AUTHORITY'}
PROFILES = {
    15: dict(master=[0x10,0x4e,7,0x25,0x0d,0x0f,0xc8,0x94],
             slave=[6,0x26,3,0x11,0x86,0x0f,0xc8,0x94], dip=0x3f),
    24: dict(master=[0x10,0x4e,7,0x25,7,7,0x90,0x65],
             slave=[6,0x26,3,0x11,0x83,7,0x90,0x65], dip=0x3e),
    31: dict(master=[0x10,0x4e,0x4b,0x0c,3,0x0b,0xdb,0x95],
             slave=[2,0x4e,0x4b,0x0c,0x83,6,0xe0,0x95], dip=0x3e),
}
NAMES = ['PROGRAMMED', 'H_OUTSIDE', 'H_BEFORE_ENTRY', 'H_INSIDE', 'H_AFTER_EXIT',
         'LINE_BEFORE', 'LINE_AFTER', 'V_BEFORE', 'V_ENTRY', 'V_INSIDE', 'V_EXIT',
         'ONE_FRAME', 'SEVERAL_FRAMES', 'HUGE_GAP', 'CPU_WORK_BEFORE',
         'CPU_WORK_AFTER', 'CPU_HELD', 'IRQ_MASKED_PENDING', 'IRQ_MASKED_EXPIRED',
         'IRQ_ACCEPTED_ISR', 'ISR_ACROSS_FRAME', 'EOI', 'HLT_WAKE', 'HLT_EOI',
         'FIFO_QUEUED', 'FIFO_DRAINED', 'SYNC_ALTERNATE', 'SYNC_RESTORED']
CASES = {i+1: dict(name=n, category=3 if i+1 in (15,16,17) else 2,
                  verdict=3 if i+1 in (14,17) else 1) for i,n in enumerate(NAMES)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def geometry(scan_class, alternate=False):
    p = PROFILES[scan_class]
    master = p['master'].copy()
    if alternate:
        master[4] += 1
    return bytes(master), bytes(p['slave'])


def clocks(scan_class, base, multiple=5, alternate=False):
    """Exact parent truncation; M=5 is compatibility metadata, not an oscillator."""
    p,_ = geometry(scan_class,alternate)
    cr = p[1]+2
    w = p[2]+256*p[3]
    x = cr+(w&31)+(w>>10)+(p[4]&63)+3
    lf = ((p[6]+256*p[7]-1)&1023)+1
    y = lf+max(1,((w>>5)&31)+(p[5]&63)+((p[6]+256*p[7])>>10))
    source,lo,hi,yl,yh = {15:(14318180//8,104,120,200,300),
                         24:(21052600//8,100,112,400,575),
                         31:(25260000//8,92,108,400,575)}[scan_class]
    xx,yy = max(lo,min(hi,x)),max(yl,min(yh,y))
    cr,lf = xx*cr//x,yy*lf//y
    h = source//xx
    frame = (base*yy//h)*multiple
    raster = frame//yy
    return dict(hclock=h,vclock=10*h//yy,rasterclock=raster,
                hsyncclock=raster*cr//xx,dispclock=raster*lf,
                vsyncclock=frame-raster*lf)


def parse_result(data, *, mode, scan_class, build_id):
    """Strict structural/freshness checks, independent of Python assert settings."""
    require(mode in MODES and scan_class in PROFILES, 'requested mode/profile')
    require(len(data)==SIZE and data[:4]==b'N4GD', 'magic or size')
    word = lambda o: struct.unpack_from('<H',data,o)[0]
    require(tuple(word(o) for o in (4,6,8,10,12,14)) ==
            (1,SIZE,RECORD,len(CASES),mode,scan_class), 'schema/count/mode/class')
    require(data[16:24].hex()==build_id, 'stale build ID')
    require(word(24)==0x201c and word(26)==28 and word(28)==scan_class,
            'terminal checkpoint/geometry')
    require(word(30)==0, 'guest must not invent host backend')
    require(struct.unpack_from('<I',data,32)[0]==32768, 'CPU progress')
    require(word(36)==2 and word(38)==0, 'IRQ count or guest failure')
    require(data[40:44]==b'\x3c\xc3\xa5\x5a' and word(44)==len(CASES), 'header guard/count')
    require(not any(data[46:HEADER]), 'header reserved')
    require(data[4084:4088]==b'\x3c\xc3\xa5\x5a', 'end guard')
    require(zlib.crc32(data[:CRC_OFFSET])==struct.unpack_from('<I',data,CRC_OFFSET)[0], 'CRC32')
    require(word(4092)==0 and word(TERMINAL_OFFSET)==2, 'reserved or nonterminal/failure state')
    records=[]
    for i in range(len(CASES)):
        o=HEADER+i*RECORD
        w=lambda n:word(o+n)
        b=data[o:o+RECORD]
        case=i+1; spec=CASES[case]
        require((w(0),w(2),w(4))==(case,case,scan_class+(100 if case==27 else 0)), 'case sequence/geometry')
        require((b[6],b[7],w(8),w(10))==(spec['category'],spec['verdict'],7,0x2000+case), 'category/verdict/flags/token')
        require(b[14:16]==b'\xff\xff', 'guest expectations are host-owned; require unknown sentinels')
        require(b[16]==((b[12]>>5)&1) and b[17]==((b[12]>>6)&1) and
                b[18]==((b[13]>>5)&1) and b[19]==((b[13]>>6)&1), 'raw scan decode')
        require((b[23],b[24],b[25])==((b[13]>>3)&1,b[12]&7,b[13]&7), 'raw engine decode')
        m,s=geometry(scan_class,case==27)
        require(b[48:56]==m and b[56:64]==s, 'requested SYNC geometry')
        require(b[64:68]==bytes([0x0f,0x0f,int(scan_class==31),0]), 'program commands/class selector')
        require(b[70:72]==b'\x00\x00' and b[72:76]==b'\x3c\xc3\xa5\x5a' and not any(b[76:]), 'record guard/reserved')
        records.append(dict(case=case,name=spec['name'],assertion=CATEGORIES[b[6]],
                            verdict='DEFERRED_TIMING_OBSERVATION' if b[7]==3 else 'OBSERVED',
                            master=b[12],slave=b[13],expected_vsync=None,expected_hblank=None,
                            vsync_master=b[16],hblank_master=b[17],vsync_slave=b[18],hblank_slave=b[19],
                            irr=b[20],isr=b[21],imr=b[22],busy=b[23],fifo_master=b[24],fifo_slave=b[25],
                            irq_count=w(26),hlt_entry=w(28),hlt_wake=w(30),
                            progress=struct.unpack_from('<I',b,32)[0],handler_isr=b[36],after_eoi=b[37],
                            saved_ip=w(38),wake_ip=w(40),saved_cs=w(42),saved_flags=w(44),
                            polls=w(46),master_sync=list(m),slave_sync=list(s),eoi_count=w(68)))
    require(not any(data[HEADER+len(CASES)*RECORD:4084]), 'unused records/padding')
    return records


def verify_result(data, *, mode, scan_class, build_id):
    records=parse_result(data,mode=mode,scan_class=scan_class,build_id=build_id)
    require(mode==1, 'NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC: no qualified fake binding evidence')
    by={r['case']:r for r in records}
    require(by[16]['progress']-by[15]['progress']==32768, 'guest CPU work not completed')
    require(by[18]['imr']&4 and by[18]['irr']&4 and by[18]['irq_count']==0, 'masked IRQ2 pending')
    require(not by[19]['irr']&4 and by[19]['irq_count']==0, 'masked request expiration')
    require(by[20]['irq_count']==1 and by[20]['isr']&4 and not by[20]['imr']&4, 'accepted IRQ2/ISR')
    require(by[21]['irq_count']==1 and by[21]['isr']&4 and not by[21]['irr']&4, 'ISR suppression/no backlog')
    require(not by[22]['isr']&4 and not by[22]['after_eoi']&4, 'EOI')
    r=by[23]
    require(r['irq_count']==2 and r['hlt_entry']==0x1111 and r['hlt_wake']==0x2222 and
            r['saved_ip']==r['wake_ip'] and r['saved_cs']==0x2000 and r['saved_flags']&0x200,
            'HLT IRQ wake and saved architectural state')
    require(r['handler_isr']&4 and by[24]['irq_count']==2 and not by[24]['isr']&4, 'HLT ISR/EOI')
    require(by[22]['eoi_count']==1 and by[24]['eoi_count']==2, 'explicit EOI sequence')
    require(all(r['master']&128 and r['slave']&128 for r in records), 'GDC status identity')
    require(by[26]['fifo_master']&4 and by[26]['fifo_slave']&4, 'FIFO drained')
    return dict(state='LEGACY_COMPATIBILITY_PROFILE_CAPTURED',mode=MODES[mode],scan_class=scan_class,
                records=records,nonclaims=['hardware timing','exact legacy H/V boundary timing',
                'CPU/machine-time independence','presentation independence','RASTER=1 timing',
                'audio','physical Ne2/GD5428'])


def reference_phase(scan_class, profile_base, ticks, alternate=False):
    """Future host expectation only: audited two-segment M_ref=5 countdown.

    ticks are reference quanta of 1/(5*B_ref) seconds. This does not service an
    emulator and must never turn a legacy trace into exact timing evidence.
    """
    require(scan_class in PROFILES and profile_base in (1996800,2457600) and
            isinstance(ticks,int) and ticks>=0,'reference phase inputs')
    c=clocks(scan_class,profile_base,5,alternate)
    d,v,r,h=(c[k] for k in ('dispclock','vsyncclock','rasterclock','hsyncclock'))
    frames,p=divmod(ticks,d+v)
    vsync=p>=d
    remaining=d+v-p if vsync else d-p
    return dict(frames=frames,phase=p,vsync=int(vsync),
                hblank=int(remaining%r<h),remaining=remaining,modulo=remaining%r)


def reference_points(scan_class, profile_base):
    """Monotone selected samples, then CPU-work/frozen and held/advance seams."""
    c=clocks(scan_class,profile_base)
    d,v,r,h=(c[k] for k in ('dispclock','vsyncclock','rasterclock','hsyncclock'))
    f=d+v
    q=[0,1,r-h,r-h+1,r+1,2*r-1,2*r+1,d-1,d,d+1,f,2*f,5*f,
       (10**12+5)*f,(10**12+5)*f,(10**12+5)*f,(10**12+5)*f+d]
    return [dict(case=i+1,reference_tick=tick,
                 first_ns_on_tick=(tick*1000000000+5*profile_base-1)//(5*profile_base),
                 expected=reference_phase(scan_class,profile_base,tick)) for i,tick in enumerate(q)]
