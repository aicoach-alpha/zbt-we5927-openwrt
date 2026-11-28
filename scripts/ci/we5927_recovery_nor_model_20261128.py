#!/usr/bin/env python3
"""Synthetic NOR safety model for exact WE5927 layout, never a router writer.

Erase size is an explicit model assumption, not measured U-Boot behavior.
No raw flash image is exported. Result cannot authorize a physical flash.
"""
import argparse
import hashlib
import json
from pathlib import Path

FLASH_SIZE=0x800000
FW_START=0x50000
FW_END=0x7f0000
ERASE_SIZE=0x10000
PROTECTED=(("u-boot",0,0x30000),("u-boot-env",0x30000,0x40000),
           ("factory",0x40000,FW_START),("art",FW_END,FLASH_SIZE))

def digest(b):
    return hashlib.sha256(b).hexdigest()

def plan(start,size,erase_policy="rounded_payload"):
    if type(start) is not int or type(size) is not int:
        raise ValueError("INVALID_RANGE_TYPE")
    if start!=FW_START or not 0<size<=FW_END-FW_START:
        raise ValueError("OUTSIDE_FIRMWARE_PARTITION")
    if erase_policy not in ("rounded_payload","whole_firmware"):
        raise ValueError("UNKNOWN_ERASE_POLICY")
    end=start+size
    erase_end=FW_END if erase_policy=="whole_firmware" else ((end+ERASE_SIZE-1)//ERASE_SIZE)*ERASE_SIZE
    if not FW_START<=start<end<=erase_end<=FW_END:
        raise ValueError("ERASE_OUTSIDE_FIRMWARE")
    return start,end,erase_end

def simulate(image,start=FW_START,erase_policy="rounded_payload"):
    if not isinstance(image,(bytes,bytearray)):
        raise ValueError("INVALID_IMAGE_TYPE")
    begin,end,erase_end=plan(start,len(image),erase_policy)
    # All contents are synthetic; no owner partition dump is used here.
    flash=bytearray(b"\x55"*FLASH_SIZE)
    for n,(_,a,b) in enumerate(PROTECTED):
        flash[a:b]=bytes([0x20+n])*(b-a)
    before={name:digest(flash[a:b]) for name,a,b in PROTECTED}
    tail_before=digest(flash[erase_end:FW_END])
    flash[begin:erase_end]=b"\xff"*(erase_end-begin)
    flash[begin:end]=image
    after={name:digest(flash[a:b]) for name,a,b in PROTECTED}
    if before!=after or digest(flash[begin:end])!=digest(image) or not all(x==255 for x in flash[end:erase_end]) or digest(flash[erase_end:FW_END])!=tail_before:
        raise RuntimeError("SYNTHETIC_INTEGRITY_CHECK_FAILED")
    return {"schema":"we5927-synthetic-nor-boundary.v1",
            "policy":erase_policy,"image_sha256":digest(image),"image_size":len(image),
            "write_start":begin,"write_end_exclusive":end,"erase_end_exclusive":erase_end,
            "erase_size_assumed":ERASE_SIZE,"protected_partition_hashes_unchanged":True,
            "payload_readback_matches":True,"outside_erase_window_unchanged":True,
            "synthetic_model_only":True,"bootloader_behavior_verified":False,
            "image_acceptance":"NOT_VERIFIED","flash_authorized":False,
            "release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if not a.image.is_file() or a.image.stat().st_size>FW_END-FW_START:
        p.error("IMAGE_NOT_REGULAR_OR_TOO_LARGE")
    image=a.image.read_bytes()
    if digest(image)!=a.sha256:p.error("IMAGE_SHA256_MISMATCH")
    result={"models":[simulate(image,erase_policy=p) for p in ("rounded_payload","whole_firmware")]}
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2);f.write("\n")
    print("SYNTHETIC_PARTITION_MODEL=PASS; MODELS=2; FLASH_AUTHORIZED=NO")
if __name__=="__main__":
    main()
