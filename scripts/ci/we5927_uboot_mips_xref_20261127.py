#!/usr/bin/env python3
"""Offline MIPS LE adjacent LUI/ADDIU or LUI/ORI string-reference reconnaissance.

Candidate references are NOT decoded HTTP control flow or acceptance proof.
No networking, router access, firmware generation or modification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from collections import defaultdict

OWNER_SHA = "b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330"
OWNER_SIZE = 196608
MARKERS = {
    "HTTP_START": b"HTTP server is starting for update",
    "HTTP_READY": b"HTTP server is ready",
    "WEB_FAILSAFE": b"Entr Web failsafe mode",
    "UPLOAD_UPGRADE": b"HTTP upload is done! Upgrading",
    "TFTP": b"tftpboot",
}

def marker_offsets(data):
    offsets = {}
    lower = data.lower()
    for label, marker in MARKERS.items():
        at = 0
        while True:
            pos = lower.find(marker.lower(), at)
            if pos < 0:
                break
            offsets.setdefault(pos, set()).add(label)
            # A reference may point at the start of a longer C string.
            start = pos
            while start > 0 and pos-start < 64 and 32 <= data[start-1] <= 126:
                start -= 1
            if start < pos and (start == 0 or data[start-1] == 0):
                offsets.setdefault(start, set()).add(label)
            at = pos+1
    return offsets

def scan(data):
    offsets = marker_offsets(data)
    groups = defaultdict(list)
    for pc in range(0, len(data)-7, 4):
        a,b = struct.unpack_from("<II", data, pc)
        reg = (a >> 16) & 31
        if a >> 26 != 15 or ((a >> 21) & 31) != 0 or reg == 0:
            continue
        op = b >> 26
        if op not in (9,13) or ((b >> 21)&31) != reg or ((b >> 16)&31) == 0:
            continue
        low = b & 0xffff
        high = (a & 0xffff) << 16
        if op == 9:
            value = (high + (low if low < 0x8000 else low-0x10000)) & 0xffffffff
        else:
            value = high | low
        for offset, labels in offsets.items():
            base = value-offset
            if not (0x80000000 <= base < 0xc0000000 and base % 4096 == 0):
                continue
            groups[base].append({"instruction_offset":pc,"string_offset":offset,
                                 "markers":sorted(labels),
                                 "pair":"LUI_ADDIU" if op==9 else "LUI_ORI"})
    candidates=[]
    for base, refs in sorted(groups.items()):
        labels=sorted({label for ref in refs for label in ref["markers"]})
        # Two distinct marker strings AND two instruction sites, not repeated hits.
        if (len(labels)<2 or len({ref["instruction_offset"] for ref in refs})<2
                or len({ref["string_offset"] for ref in refs})<2):
            continue
        candidates.append({"candidate_base":f"0x{base:08x}","markers":labels,
                           "references":refs})
    return {"schema":"we5927-uboot-adjacent-mips-xrefs.v1",
            "marker_labels_found":sorted({x for v in offsets.values() for x in v}),
            "candidate_groups":candidates,
            "status":"CANDIDATE_XREFS_ONLY" if candidates else "NO_CANDIDATE_XREFS",
            "limitations":["MIPS little-endian adjacent instruction pairs only",
              "data can resemble instructions; relocation and control flow not verified",
              "no candidate does not establish absence of handler"],
            "http_handler_control_flow":"NOT_VERIFIED",
            "image_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,
            "router_contacted":False}

def verified_scan(first, second):
    images=[Path(p).read_bytes() for p in (first,second)]
    if any(len(data)!=OWNER_SIZE or hashlib.sha256(data).hexdigest()!=OWNER_SHA
           for data in images) or images[0]!=images[1]:
        raise ValueError("EXACT_MTD0_BACKUP_SHA_OR_SIZE_MISMATCH")
    result=scan(images[0])
    result["owner_mtd0_sha256"]=OWNER_SHA
    result["both_backups_verified"]=True
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--nov23",required=True,type=Path)
    p.add_argument("--nov25",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if args.nov23.resolve()==args.nov25.resolve():
        p.error("two distinct historical backups required")
    result=verified_scan(args.nov23,args.nov25)
    with args.output.open("x",encoding="utf-8") as output:
        json.dump(result,output,indent=2)
        output.write("\n")
    print("MODE=LOCAL_ONLY; ROUTER_CONTACTED=NO; FLASH_AUTHORIZED=NO")
    print("XREF_STATUS="+result["status"])
    print("CANDIDATE_GROUPS="+str(len(result["candidate_groups"])))
    print("HTTP_HANDLER_CONTROL_FLOW=NOT_VERIFIED")

if __name__=="__main__":
    main()
