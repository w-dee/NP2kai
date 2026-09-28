#!/usr/bin/env python3
"""Supporting FMP event/producer trends; live PCM is never a byte oracle."""
import argparse
import hashlib
import json
from pathlib import Path


def rows(path):
    return [tuple(map(int,line.split(','))) for line in path.read_text().splitlines()
            if line and not line.startswith('#')]


def load(root,backend,mode):
    folder=root/f'{backend}-{mode}'
    events=rows(folder/'events.csv')
    blocks=rows(folder/'blocks.csv')
    frames=(folder/'producer.s32le').stat().st_size//8
    assert blocks and frames==sum(block[3] for block in blocks)
    rate=blocks[0][4]
    assert all(block[4]==rate for block in blocks)
    first=next(i for i,event in enumerate(events) if event[3]==0x28 and event[4]&0xf0)
    return events[first:],dict(raw_events=len(events),first_keyon_index=first,
        producer_frames=frames,rate=rate,producer_duration_s=frames/rate,
        generation_calls=len(blocks),frames_by_origin={str(origin):sum(b[3] for b in blocks if b[5]==origin) for origin in sorted(set(b[5] for b in blocks))})


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,required=True,help='directory containing BACKEND-off and BACKEND-candidate')
    ap.add_argument('--backend',choices=['i286','ia32'],required=True)
    ap.add_argument('--compare-mode',choices=['before','candidate'],default='candidate')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    off,off_summary=load(args.root,args.backend,'off')
    candidate,candidate_summary=load(args.root,args.backend,args.compare_mode)
    limit=min(len(off),len(candidate))
    prefix=next((i for i in range(limit) if off[i][3:5]!=candidate[i][3:5]),limit)
    result=dict(backend=args.backend,compare_mode=args.compare_mode,off=off_summary,compared=candidate_summary,
                compared_event_prefix=limit,identical_event_prefix=prefix,
                raw_event_sequence_identity=prefix==limit and len(off)==len(candidate))
    if prefix<limit:result['first_difference']=dict(index=prefix,off=off[prefix],candidate=candidate[prefix])
    if prefix>1:
        ref=off[:prefix];new=candidate[:prefix]
        off_wall=ref[-1][0]-ref[0][0]
        new_wall=new[-1][0]-new[0][0]
        off_frames=ref[-1][2]-ref[0][2]
        new_frames=new[-1][2]-new[0][2]
        result['event_time_scale']=new_wall/off_wall if off_wall else None
        result['producer_frontier_span_frames']=dict(off=off_frames,candidate=new_frames)
        result['producer_duration_scale']=((new_frames/new[0][5])/(off_frames/ref[0][5])) if off_frames else None
        result['raw_event_identity_sha256']=hashlib.sha256(bytes(v for event in ref for v in [event[3]&255,event[3]>>8,event[4]])).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
