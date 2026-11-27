#!/usr/bin/env python3
"""Read-only pointer-table reconnaissance. A candidate mapping is not a recovery proof."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from collections import defaultdict
from we5927_uboot_mips_xref_20261127 import OWNER_SHA, OWNER_SIZE, MARKERS

def inspect(data):
    words = struct.unpack_from("<%dI" % (len(data)//4), data)
    candidates = defaultdict(list)
    # Detect runs of linked-table-looking pointer pairs. Require alignment,
    # local targets, and a consistent page-aligned mapping; not arbitrary words.
    for i in range(len(words)-1):
        pos = i*4
        a,b = words[i:i+2]
        if a < 0x80000000 or a >= 0xc0000000 or b-a != 8:
            continue
        for delta in (-12,-8,-4,0,4,8,12):
            target = pos+delta
            base = a-target
            if target >= 0 and target+8 < len(data) and 0x80000000 <= base < 0xc0000000 and base % 4096 == 0:
                candidates[(base,delta)].append(pos)
    groups=[]
    for (base,delta), positions in sorted(candidates.items()):
        runs=[]
        run=[]
        for p in positions:
            if run and p-run[-1] != 8:
                if len(run)>=16: runs.append(run)
                run=[]
            run.append(p)
        if len(run)>=16: runs.append(run)
        if not runs: continue
        hits={}
        for name,marker in MARKERS.items():
            off=data.lower().find(marker.lower())
            hits[name]=[i*4 for i,v in enumerate(words) if off>=0 and v==base+off]
        groups.append({"base_candidate":hex(base),"pair_target_delta":delta,
                       "longest_consecutive_pairs":max(map(len,runs)),
                       "table_runs":[{"offset":r[0],"pairs":len(r)} for r in runs],
                       "direct_marker_pointer_offsets":hits})
    return {"schema":"we5927-uboot-linked-table-recon.v1","candidates":groups,
            "status":"CANDIDATE_MAPPING_ONLY" if groups else "NO_CANDIDATE_MAPPING",
            "http_handler_control_flow":"NOT_VERIFIED","image_acceptance":"NOT_VERIFIED",
            "physical_recovery":"NOT_TESTED","flash_authorized":False,
            "release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    data=args.image.read_bytes()
    if len(data)!=OWNER_SIZE or hashlib.sha256(data).hexdigest()!=OWNER_SHA:
        p.error("EXACT_MTD0_SHA_OR_SIZE_MISMATCH")
    report=inspect(data)
    report["owner_mtd0_sha256"]=OWNER_SHA
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2); f.write("\n")
    print("MAPPING_STATUS="+report["status"])
    print("MAPPING_GROUPS="+str(len(report["candidates"])))
    print("HTTP_HANDLER_CONTROL_FLOW=NOT_VERIFIED; FLASH_AUTHORIZED=NO")

if __name__=="__main__":
    main()
