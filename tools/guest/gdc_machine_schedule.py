# SPDX-License-Identifier: MIT
"""Additional host schedules evaluated by the committed N4 phase reference."""
from gdc_contract import clocks, reference_points, reference_phase

SCHEDULES=('canonical','frozen_repeat','boundary_variants','fractional_and_partitioned')
def points(scan_class,base,schedule='canonical'):
    if schedule not in SCHEDULES:raise ValueError('unknown schedule')
    result=reference_points(scan_class,base)
    c=clocks(scan_class,base);r,h,d,v=(c[k] for k in ('rasterclock','hsyncclock','dispclock','vsyncclock'))
    replacements={}
    if schedule=='frozen_repeat':replacements={i:0 for i in range(1,8)}
    if schedule=='boundary_variants':
        replacements=dict(zip(range(2,8),[r-h-1,r-h,r-h+1,r-1,r,r+1]))
        replacements.update({9:d+1,10:d+v-1,11:d+v+1})
    for item in result:
        q=replacements.get(item['case'],item['reference_tick'])
        item.update(reference_tick=q,first_ns_on_tick=(q*1000000000+5*base-1)//(5*base),expected=reference_phase(scan_class,base,q))
    return result
