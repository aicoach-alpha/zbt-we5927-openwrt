#!/usr/bin/env python3
"""Offline notification caller and return-branch pattern reconnaissance.

Recognizes only exact MIPS instruction shapes. Does not emulate the callee,
infer semantics, or establish safe flash behavior.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from we5927_uboot_mips_xref_20261127 import OWNER_SHA, OWNER_SIZE
from we5927_uboot_pic_got_20261127 import inspect as pic_scan, signed16
from we5927_uboot_pointer_table_20261127 import inspect as mapping_scan
from we5927_uboot_message_sink_20261127 import inspect as sink_scan

def inspect(data):
    pic=pic_scan(data)
    maps={int(c["base_candidate"],16) for c in mapping_scan(data)["candidates"]}
    gp=pic["gp_relative_offset"]
    sink={c["callee_candidate_offset"] for c in sink_scan(data)["shared_callee_candidates"]
          if c["classification"]=="LIKELY_MESSAGE_SINK"}
    result=[]
    if len(maps)==1 and gp is not None and sink:
        base=next(iter(maps))
        w=struct.unpack_from("<%dI"%(len(data)//4),data)
        def got(ins):
            if ins&0xffff0000!=0x8f990000:return None
            slot=gp+signed16(ins)
            if slot%4 or not 0<=slot<=len(data)-4:return None
            v=w[slot//4]-base
            return v if v%4==0 and 0<=v<len(data) else None
        def prologue(i):
            return (0<=i<len(w)-2 and w[i]&0xffff0000==0x3c1c0000
                    and w[i+1]&0xffff0000==0x279c0000 and w[i+2]==0x0399e021)
        for ref in pic["resolved_static_patterns"]:
            if ref["marker"]!="UPLOAD_UPGRADE" or ref["callee_candidate_offset"] not in sink:continue
            i=ref["callsite_offset"]//4
            start=next((j for j in range(i,max(-1,i-512),-1) if prologue(j)),None)
            if start is None:continue
            # Confirm a state==2 dispatch with direct branch to this message block.
            # The block may begin before the argument-loading site; do not equate
            # arbitrary preceding code with an entry point.
            state_targets=[]
            for j in range(start,min(start+24,len(w)-2)):
                if w[j]==0x24020002 and w[j+1]&0xffff0000==0x10820000:
                    t=j+2+signed16(w[j+1])
                    if start<=t<=i and i-t<=32:
                        state_targets.append(t)
            if len(state_targets)!=1:continue
            for j in range(len(w)-8):
                # exact caller pattern: notify(2), restore gp, load two args,
                # indirect call, then bltz v0. Both args must be memory loads.
                if got(w[j])!=start*4 or w[j+1]!=0x0320f809 or w[j+2]!=0x24040002:continue
                if w[j+3]&0xffff0000!=0x8fbc0000:continue
                if w[j+4]>>26!=35 or (w[j+4]>>16)&31!=4:continue
                callee=got(w[j+5])
                if callee is None or callee in sink or callee==start*4:continue
                if w[j+6]!=0x0320f809 or w[j+7]>>26!=35 or (w[j+7]>>16)&31!=5:continue
                b=j+8
                if w[b]&0xffff0000!=0x04400000:continue
                target=b+1+signed16(w[b])
                if not 0<=target<len(w):continue
                result.append({"notification_function_offset":start*4,
                    "notification_state":2,"notification_call_offset":(j+1)*4,
                    "next_callee_candidate_offset":callee,
                    "next_call_offset":(j+6)*4,"return_branch":"BLTZ_V0",
                    "negative_return_target_offset":target*4,
                    "callee_semantics":"UNKNOWN"})
    return {"schema":"we5927-uboot-notification-return-branch.v1",
            "candidates":result,
            "status":"STATIC_RETURN_BRANCH_CANDIDATES" if result else "NOT_RESOLVED",
            "firmware_validator":"NOT_VERIFIED","flash_writer":"NOT_VERIFIED",
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
    report=inspect(data);report["owner_mtd0_sha256"]=OWNER_SHA
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2);f.write("\n")
    print("RETURN_BRANCH_STATUS="+report["status"])
    print("CANDIDATES="+str(len(report["candidates"])))
    print("FLASH_AUTHORIZED=NO; ROUTER_CONTACTED=NO")
if __name__=="__main__":
    main()
