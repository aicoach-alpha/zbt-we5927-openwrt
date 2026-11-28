#!/usr/bin/env python3
"""Single-slot, synthetic power-interruption risk model; no physical flash."""
import argparse
import hashlib
import json
from pathlib import Path
from we5927_recovery_nor_model_20261128 import FLASH_SIZE,FW_START,FW_END,ERASE_SIZE,PROTECTED,plan
from we5927_recovery_image_format_gate_20261127 import VENDOR_SHA,VECI_SHA,MTD3_LIMIT
def sha(b):return hashlib.sha256(b).hexdigest()
def simulate(old,new,policy):
    if not isinstance(old,bytes) or not isinstance(new,bytes):raise ValueError("IMMUTABLE_BYTES_REQUIRED")
    plan(FW_START,len(old)); begin,end,erase_end=plan(FW_START,len(new),policy)
    flash=bytearray(b"\xff"*FLASH_SIZE)
    for n,(_,a,b) in enumerate(PROTECTED):flash[a:b]=bytes([0x20+n])*(b-a)
    flash[begin:begin+len(old)]=old
    protected={n:sha(flash[a:b]) for n,a,b in PROTECTED}
    old_hash=sha(old);new_hash=sha(new)
    points=[]
    def checkpoint(label,verified=False):
        if protected!={n:sha(flash[a:b]) for n,a,b in PROTECTED}:raise RuntimeError("PROTECTED_PARTITION_CHANGED")
        old_match=sha(flash[begin:begin+len(old)])==old_hash
        new_match=sha(flash[begin:end])==new_hash
        points.append({"stage":label,"old_payload_exact":old_match,"new_payload_exact":new_match,
          "protected_hashes_unchanged":True,"new_payload_readback_verified":verified,
          "neither_payload_exact":not old_match and not new_match,"bootability":"UNKNOWN"})
    checkpoint("before_erase")
    flash[begin:begin+ERASE_SIZE]=b"\xff"*ERASE_SIZE
    checkpoint("after_first_sector_erase")
    flash[begin+ERASE_SIZE:erase_end]=b"\xff"*(erase_end-begin-ERASE_SIZE)
    checkpoint("after_erase")
    half=max(1,len(new)//2)
    flash[begin:begin+half]=new[:half]
    checkpoint("mid_program")
    flash[begin+half:end]=new[half:]
    checkpoint("after_program_before_verify")
    if sha(flash[begin:end])!=new_hash:raise RuntimeError("READBACK_MISMATCH")
    checkpoint("after_readback",True)
    return {"policy":policy,"erase_size_assumed":ERASE_SIZE,"checkpoints":points,
            "synthetic_model_only":True,"bootloader_behavior_verified":False,"automatic_rollback_proven":False,
            "physical_recovery":"NOT_TESTED","flash_authorized":False,"release_permitted":False,"router_contacted":False}
def main():
    p=argparse.ArgumentParser()
    for k in ("oem","veci","output"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    with a.oem.open("rb") as f:o=f.read(MTD3_LIMIT+1)
    with a.veci.open("rb") as f:v=f.read(MTD3_LIMIT+1)
    if sha(o)!=VENDOR_SHA or sha(v)!=VECI_SHA:p.error("EXACT_IMAGE_HASH_MISMATCH")
    models=[]
    for name,old,new in (("reference_to_candidate",o,v),("candidate_to_reference",v,o)):
        for policy in ("rounded_payload","whole_firmware"):
            models.append({"direction":name,**simulate(old,new,policy)})
    r={"schema":"we5927-power-interruption-synthetic.v1","models":models,
       "old_images_are_research_inputs_not_installed_state":True,"flash_authorized":False}
    with a.output.open("x",encoding="utf-8") as f:json.dump(r,f,indent=2);f.write("\n")
    print("MODELS="+str(len(models))+"; CHECKPOINTS="+str(sum(len(m["checkpoints"]) for m in models))+"; FLASH_AUTHORIZED=NO")
if __name__=="__main__":main()
