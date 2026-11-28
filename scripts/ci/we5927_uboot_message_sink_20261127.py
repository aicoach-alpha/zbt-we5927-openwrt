#!/usr/bin/env python3
"""Conservative offline classification of shared HTTP message-call candidates.
Never treats a message sink as a validator or authorizes recovery.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from we5927_uboot_mips_xref_20261127 import OWNER_SHA, OWNER_SIZE
from we5927_uboot_pic_got_20261127 import inspect as pic_scan, signed16
from we5927_uboot_pointer_table_20261127 import inspect as mapping_scan

def text_at(data, offset):
    if not 0 <= offset < len(data):
        return None
    chunk=data[offset:offset+160]
    end=chunk.find(b"\0")
    if end<4:
        return None
    raw=chunk[:end]
    if any(not (32<=b<127 or b in (9,10,13)) for b in raw):
        return None
    return bytes(raw)

def inspect(data):
    pic=pic_scan(data)
    mapping={int(c["base_candidate"],16) for c in mapping_scan(data)["candidates"]}
    gp=pic["gp_relative_offset"]
    targets={r["callee_candidate_offset"] for r in pic["resolved_static_patterns"]}
    summaries=[]
    if len(mapping)==1 and gp is not None:
        base=next(iter(mapping))
        w=struct.unpack_from("<%dI"%(len(data)//4),data)
        def lookup(ins):
            p=gp+signed16(ins)
            if p%4 or not 0<=p<=len(data)-4:return None
            v=w[p//4]-base
            return v if 0<=v<len(data) else None
        for target in sorted(targets):
            sites=[]
            for i in range(len(w)-3):
                a,b,c,d=w[i:i+4]
                if (a&0xffff0000,b&0xffff0000,c&0xffff0000,d&0xffff0000)!=(0x8f840000,0x8f990000,0x10000000,0x24840000):
                    continue
                branch=i+3+signed16(c)
                if not 0<=branch<len(w)-1 or w[branch]!=0x0320f809:
                    continue
                arg=lookup(a)
                if arg is None or lookup(b)!=target:continue
                msg=text_at(data,arg+signed16(d))
                if msg is not None:sites.append(msg)
            distinct=set(sites)
            non_http=sum(b"http" not in m.lower() for m in distinct)
            newline=sum(b"\n" in m for m in distinct)
            percent=sum(b"%" in m for m in distinct)
            # A variadic-like register spill pattern is corroboration only.
            prologue=w[target//4:target//4+20]
            spills={((a>>16)&31) for a in prologue if a>>26==43 and (a>>21)&31==29}
            spill_like={5,6,7}<=spills
            likely=len(distinct)>=8 and non_http>=4 and newline>=4 and spill_like
            summaries.append({"callee_candidate_offset":target,
                "matched_text_calls":len(sites),"distinct_text_arguments":len(distinct),
                "non_http_text_arguments":non_http,"newline_text_arguments":newline,
                "percent_text_arguments":percent,"argument_register_spills":spill_like,
                "classification":"LIKELY_MESSAGE_SINK" if likely else "UNCLASSIFIED",
                "validator_proven":False})
    return {"schema":"we5927-uboot-message-sink-recon.v1",
            "shared_callee_candidates":summaries,
            "validation_control_flow":"NOT_VERIFIED","image_acceptance":"NOT_VERIFIED",
            "physical_recovery":"NOT_TESTED","flash_authorized":False,
            "release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    data=a.image.read_bytes()
    if len(data)!=OWNER_SIZE or hashlib.sha256(data).hexdigest()!=OWNER_SHA:
        p.error("EXACT_MTD0_SHA_OR_SIZE_MISMATCH")
    result=inspect(data)
    result["owner_mtd0_sha256"]=OWNER_SHA
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2);f.write("\n")
    print("MESSAGE_SINK_CANDIDATES="+str(sum(x["classification"]=="LIKELY_MESSAGE_SINK" for x in result["shared_callee_candidates"])))
    print("VALIDATION_CONTROL_FLOW=NOT_VERIFIED; FLASH_AUTHORIZED=NO")
if __name__=="__main__":
    main()
