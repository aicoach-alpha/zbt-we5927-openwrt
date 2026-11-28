#!/usr/bin/env python3
"""Offline synthetic restore retry following three interrupted update stages.
Both erase policies model assumptions; no actual U-Boot code or flash writes.
"""
import argparse
import json
from pathlib import Path
from we5927_recovery_nor_model_20261128 import FLASH_SIZE,FW_START,FW_END,ERASE_SIZE,PROTECTED,plan,digest
from we5927_recovery_image_format_gate_20261127 import VENDOR_SHA,VECI_SHA,MTD3_LIMIT

STAGES=("first_sector_erased","erase_finished","mid_program")
POLICIES=("rounded_payload","whole_firmware")
def experiment(old,new,update_policy,retry_policy,stage):
    if not isinstance(old,bytes) or not isinstance(new,bytes):raise ValueError("IMMUTABLE_BYTES_REQUIRED")
    if stage not in STAGES:raise ValueError("UNKNOWN_INTERRUPT_STAGE")
    a,b,e=plan(FW_START,len(new),update_policy)
    _,old_end,restore_end=plan(FW_START,len(old),retry_policy)
    flash=bytearray(b"\xff"*FLASH_SIZE)
    for n,(_,lo,hi) in enumerate(PROTECTED):flash[lo:hi]=bytes([0x20+n])*(hi-lo)
    flash[a:old_end]=old
    protected={n:digest(flash[lo:hi]) for n,lo,hi in PROTECTED}
    original=digest(flash[a:FW_END])
    if stage=="first_sector_erased":
        flash[a:a+ERASE_SIZE]=b"\xff"*ERASE_SIZE
    else:
        flash[a:e]=b"\xff"*(e-a)
        if stage=="mid_program":
            half=max(1,len(new)//2);flash[a:a+half]=new[:half]
    interrupted=digest(flash[a:old_end])!=digest(old) and digest(flash[a:b])!=digest(new)
    flash[a:restore_end]=b"\xff"*(restore_end-a)
    flash[a:old_end]=old
    if protected!={n:digest(flash[lo:hi]) for n,lo,hi in PROTECTED}:raise RuntimeError("PROTECTED_CHANGED")
    if digest(flash[a:old_end])!=digest(old):raise RuntimeError("RESTORED_PAYLOAD_MISMATCH")
    return {"stage":stage,"update_policy":update_policy,"retry_policy":retry_policy,
            "interruption_neither_exact_payload":interrupted,
            "restore_payload_exact":True,"entire_firmware_partition_restored":digest(flash[a:FW_END])==original,
            "protected_hashes_unchanged":True,"bootability":"UNKNOWN",
            "synthetic_model_only":True,"physical_recovery":"NOT_TESTED","flash_authorized":False}

def main():
    p=argparse.ArgumentParser()
    for k in ("oem","veci","output"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    with a.oem.open("rb") as f:o=f.read(MTD3_LIMIT+1)
    with a.veci.open("rb") as f:v=f.read(MTD3_LIMIT+1)
    if digest(o)!=VENDOR_SHA or digest(v)!=VECI_SHA:p.error("EXACT_HASH_MISMATCH")
    rows=[]
    for direction,old,new in (("oem_to_veci",o,v),("veci_to_oem",v,o)):
        for update in POLICIES:
            for retry in POLICIES:
                for stage in STAGES:rows.append({"direction":direction,**experiment(old,new,update,retry,stage)})
    result={"schema":"we5927-synthetic-restore-retry.v1","cases":rows,"installed_state_not_verified":True,
            "flash_authorized":False,"router_contacted":False,"release_permitted":False}
    with a.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2);f.write("\n")
    print("CASES="+str(len(rows))+"; PAYLOAD_RESTORED="+str(sum(r["restore_payload_exact"] for r in rows))+"; FULL_PARTITION_RESTORED="+str(sum(r["entire_firmware_partition_restored"] for r in rows))+"; FLASH_AUTHORIZED=NO")
if __name__=="__main__":main()
