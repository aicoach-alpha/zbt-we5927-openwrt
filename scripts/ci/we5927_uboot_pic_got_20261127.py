#!/usr/bin/env python3
"""Offline PIC/GOT reference resolution for exact-owner MTD0.
Static local call-site patterns, not executable handler or image acceptance proof.
"""
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from we5927_uboot_mips_xref_20261127 import OWNER_SHA, OWNER_SIZE, MARKERS
from we5927_uboot_pointer_table_20261127 import inspect as mapping_scan

def signed16(n):
    n &= 0xffff
    return n if n < 0x8000 else n-0x10000

def inspect(data):
    w=struct.unpack_from("<%dI"%(len(data)//4),data)
    candidates=mapping_scan(data)["candidates"]
    mappings=sorted({int(c["base_candidate"],16) for c in candidates})
    gp_votes=Counter()
    for i in range(len(w)-2):
        a,b,c=w[i:i+3]
        if a & 0xffff0000 == 0x3c1c0000 and b & 0xffff0000 == 0x279c0000 and c == 0x0399e021:
            gp_votes[(i*4+((a&0xffff)<<16)+signed16(b))&0xffffffff]+=1
    gp=None
    if gp_votes:
        offset,count=gp_votes.most_common(1)[0]
        if count>=8 and count==sum(gp_votes.values()) and offset%4==0 and 0<=offset<len(data)-3:
            gp=offset
    refs=[]
    if len(mappings)==1 and gp is not None:
        base=mappings[0]
        marker_offsets={data.lower().find(v.lower()):k for k,v in MARKERS.items()}
        marker_offsets.pop(-1,None)
        def lookup(ins):
            slot=gp+signed16(ins)
            if slot%4 or not 0<=slot<=len(data)-4: return None
            target=w[slot//4]-base
            return target if 0<=target<len(data) else None
        for i in range(len(w)-3):
            a,b,c,d=w[i:i+4]
            # Exact argument load, indirect callee load, unconditional branch,
            # and ADDIU in the branch delay slot. No guessing through clobbers.
            if (a&0xffff0000,b&0xffff0000,c&0xffff0000,d&0xffff0000)!=(0x8f840000,0x8f990000,0x10000000,0x24840000):
                continue
            arg=lookup(a); callee=lookup(b)
            if arg is None or callee is None or callee%4: continue
            target=arg+signed16(d)
            branch=i+3+signed16(c)
            if target not in marker_offsets or not 0<=branch<len(w)-1: continue
            if w[branch]!=0x0320f809: continue
            refs.append({"marker":marker_offsets[target],"callsite_offset":i*4,
                         "shared_call_offset":branch*4,"callee_candidate_offset":callee})
    return {"schema":"we5927-uboot-pic-got-recon.v1",
            "mapping_candidates":len(mappings),"gp_consensus_votes":gp_votes[gp] if gp is not None else 0,
            "gp_relative_offset":gp,"resolved_static_patterns":refs,
            "status":"STATIC_CALLSITE_CANDIDATES" if refs else "NO_RESOLVED_CALLSITE",
            "http_handler_control_flow":"PARTIAL_STATIC_EVIDENCE" if refs else "NOT_VERIFIED",
            "image_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    data=a.image.read_bytes()
    if len(data)!=OWNER_SIZE or hashlib.sha256(data).hexdigest()!=OWNER_SHA:
        p.error("EXACT_MTD0_SHA_OR_SIZE_MISMATCH")
    r=inspect(data)
    r["owner_mtd0_sha256"]=OWNER_SHA
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(r,f,indent=2); f.write("\n")
    print("PIC_STATUS="+r["status"])
    print("GP_VOTES="+str(r["gp_consensus_votes"]))
    print("STATIC_PATTERNS="+str(len(r["resolved_static_patterns"])))
    print("FLASH_AUTHORIZED=NO; ROUTER_CONTACTED=NO")
if __name__=="__main__":
    main()
