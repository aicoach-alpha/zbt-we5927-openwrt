#!/usr/bin/env python3
"""Dirty-tail recovery experiments on synthetic NOR; never physical flash.

Distinguishes original full-partition identity, payload identity and clean
tail. Synthetic residual data is deliberately not actual owner data.
"""
import argparse
import json
from pathlib import Path
from we5927_recovery_nor_model_20261128 import FLASH_SIZE,FW_START,FW_END,ERASE_SIZE,PROTECTED,plan,digest
from we5927_recovery_image_format_gate_20261127 import VENDOR_SHA,VECI_SHA,MTD3_LIMIT
from we5927_recovery_retry_20261128 import STAGES,POLICIES

def experiment(old,new,update_policy,retry_policy,stage):
    if not isinstance(old,bytes) or not isinstance(new,bytes):raise ValueError("IMMUTABLE_BYTES_REQUIRED")
    if stage not in STAGES:raise ValueError("UNKNOWN_INTERRUPT_STAGE")
    a,b,e=plan(FW_START,len(new),update_policy)
    _,old_end,restore_end=plan(FW_START,len(old),retry_policy)
    flash=bytearray(b"\xff"*FLASH_SIZE)
    for n,(_,lo,hi) in enumerate(PROTECTED):flash[lo:hi]=bytes([0x20+n])*(hi-lo)
    flash[a:old_end]=old
    # Non-erased synthetic tail represents possible old overlay/residual data.
    flash[old_end:FW_END]=b"\x55"*(FW_END-old_end)
    protected={n:digest(flash[lo:hi]) for n,lo,hi in PROTECTED}
    original=digest(flash[a:FW_END])
    original_tail=digest(flash[old_end:FW_END])
    if stage=="first_sector_erased":
        flash[a:a+ERASE_SIZE]=b"\xff"*ERASE_SIZE
    else:
        flash[a:e]=b"\xff"*(e-a)
        if stage=="mid_program":
            half=max(1,len(new)//2);flash[a:a+half]=new[:half]
    flash[a:restore_end]=b"\xff"*(restore_end-a)
    flash[a:old_end]=old
    if protected!={n:digest(flash[lo:hi]) for n,lo,hi in PROTECTED}:raise RuntimeError("PROTECTED_CHANGED")
    if digest(flash[a:old_end])!=digest(old):raise RuntimeError("RESTORED_PAYLOAD_MISMATCH")
    tail=flash[old_end:FW_END]
    return {"stage":stage,"update_policy":update_policy,"retry_policy":retry_policy,
            "restore_payload_exact":True,"original_partition_exact":digest(flash[a:FW_END])==original,
            "original_tail_exact":digest(tail)==original_tail,
            "tail_non_erased_bytes":len(tail)-tail.count(255),
            "tail_all_erased":tail.count(255)==len(tail),
            "protected_hashes_unchanged":True,"configuration_restore":"NOT_VERIFIED",
            "bootability":"UNKNOWN","synthetic_model_only":True,"flash_authorized":False}

def main():
    p=argparse.ArgumentParser()
    for k in ("oem","veci","output"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    with a.oem.open("rb") as f:o=f.read(MTD3_LIMIT+1)
    with a.veci.open("rb") as f:v=f.read(MTD3_LIMIT+1)
    if digest(o)!=VENDOR_SHA or digest(v)!=VECI_SHA:p.error("EXACT_HASH_MISMATCH")
    rows=[{"direction":direction,**experiment(old,new,u,r,s)}
          for direction,old,new in (("oem_to_veci",o,v),("veci_to_oem",v,o))
          for u in POLICIES for r in POLICIES for s in STAGES]
    result={"schema":"we5927-dirty-tail-restore-model.v1","cases":rows,
            "original_tail_is_synthetic":True,"physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}
    with a.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2);f.write("\n")
    for k in ("restore_payload_exact","original_partition_exact","tail_all_erased","protected_hashes_unchanged"):
        print(k.upper()+"="+str(sum(r[k] for r in rows))+"/"+str(len(rows)))
    print("FLASH_AUTHORIZED=NO")
if __name__=="__main__":main()
