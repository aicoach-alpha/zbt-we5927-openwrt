#!/usr/bin/env python3
"""Exact static wrapper pattern: local evidence only, no emulation or flash.
Recognizes firmware-mode tail-call arguments, not the actual write semantics.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from we5927_uboot_mips_xref_20261127 import OWNER_SHA,OWNER_SIZE
from we5927_uboot_return_branch_20261127 import inspect as branch_scan
from we5927_uboot_pic_got_20261127 import inspect as pic_scan,signed16
from we5927_uboot_pointer_table_20261127 import inspect as mapping_scan

def inspect(data):
    branch=branch_scan(data)
    pic=pic_scan(data)
    maps={int(c["base_candidate"],16) for c in mapping_scan(data)["candidates"]}
    gp=pic["gp_relative_offset"]
    w=struct.unpack_from("<%dI"%(len(data)//4),data)
    found=[]
    if len(maps)==1 and gp is not None:
        base=next(iter(maps))
        for entry in sorted({c["next_callee_candidate_offset"] for c in branch["candidates"]}):
            i=entry//4
            if entry%4 or i<0 or i+53>len(w):continue
            p=w[i:i+53]
            # Fixed, independently observed wrapper instruction shape. Fail
            # closed when control flow or register moves differ.
            if p[7]!=0x00808021 or p[9]!=0x24020001 or p[11]!=0x14a20009:continue
            if p[23]!=0x14a00009 or p[28]!=0x02003021:continue
            if p[29]!=0x3c048100 or p[31]!=0x1000000c or p[32]&0xffff0000!=0x3c050000:continue
            if p[33]!=0x24020002 or p[34]!=0x14a2000d:continue
            if p[44]!=0x8fbf001c or p[45]!=0x8fb00018 or p[46]!=0x03200008 or p[47]!=0x27bd0020:continue
            if p[50]!=0x2402ffff or p[51]!=0x03e00008:continue
            # The same indirect target is loaded by all three paths.
            loads=[p[j] for j in (18,30,42)]
            if len(set(loads))!=1 or loads[0]&0xffff0000!=0x8f990000:continue
            slot=gp+signed16(loads[0])
            if slot%4 or not 0<=slot<=len(data)-4:continue
            target=w[slot//4]-base
            if not 0<=target<len(data)-4 or target%4:continue
            dest=(p[32]&0xffff)<<16
            found.append({"wrapper_offset":entry,"common_callee_candidate_offset":target,
                          "mode_dispatch_detected":True,"ordinary_firmware_path_destination_argument":dest,
                          "length_argument_from_input":True,
                          "alternate_modes_exist":True,"unknown_mode_negative_return_pattern":True,
                          "destination_matches_expected_firmware_start":dest==0x50000,
                          "callee_write_or_validation_semantics":"UNKNOWN"})
    return {"schema":"we5927-uboot-mode-wrapper-recon.v1","candidates":found,
            "status":"STATIC_WRAPPER_CANDIDATE" if found else "NOT_RESOLVED",
            "flash_bounds_enforced_by_bootloader":"NOT_VERIFIED",
            "image_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--image",required=True,type=Path);p.add_argument("--output",required=True,type=Path);a=p.parse_args()
    d=a.image.read_bytes()
    if len(d)!=OWNER_SIZE or hashlib.sha256(d).hexdigest()!=OWNER_SHA:p.error("EXACT_MTD0_SHA_OR_SIZE_MISMATCH")
    r=inspect(d);r["owner_mtd0_sha256"]=OWNER_SHA
    with a.output.open("x",encoding="utf-8") as f:json.dump(r,f,indent=2);f.write("\n")
    print("MODE_WRAPPER_STATUS="+r["status"]);print("CANDIDATES="+str(len(r["candidates"])))
    print("FLASH_AUTHORIZED=NO; ROUTER_CONTACTED=NO")
if __name__=="__main__":main()
