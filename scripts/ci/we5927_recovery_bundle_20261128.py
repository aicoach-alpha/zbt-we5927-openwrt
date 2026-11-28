#!/usr/bin/env python3
"""Pinned research bundle: actual signature and offline format/model evidence.
No physical test, runtime OTA permission or rescue approval.
"""
import argparse
import json
from pathlib import Path
from we5927_recovery_image_format_gate_20261127 import MTD3_LIMIT,VENDOR_SHA,VECI_SHA
from we5927_shared_recovery_model_20261128 import evaluate
from we5927_exact_candidate_crypto_20261128 import check

def run(oem,veci,key,fwtool,ucert,usign):
    # Crypto is required before any format/model result is presented as a bundle.
    crypto=check(veci,key,fwtool,ucert,usign)
    if crypto.get("image_sha256")!=VECI_SHA or crypto.get("signature_against_pinned_nas_public_key")!="PASS":
        raise ValueError("CRYPTO_EVIDENCE_MISMATCH")
    signed=evaluate(veci,"signed_veci_candidate",VECI_SHA)
    vendor=evaluate(oem,"oem_reference",VENDOR_SHA)
    if any(x["format"]["sha256"]!=expected or x["format_and_model_status"]!="PASS"
           for x,expected in ((signed,VECI_SHA),(vendor,VENDOR_SHA))):
        raise ValueError("FORMAT_EVIDENCE_MISMATCH")
    return {"schema":"we5927-pinned-offline-recovery-bundle.v1",
            "crypto":crypto,"signed_candidate":signed,"oem_reference":vendor,
            "offline_bundle":"PASS","oem_signature":"NOT_VERIFIED",
            "bootloader_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}

def read(path,n):
    with path.open("rb") as f:return f.read(n+1)

def main():
    p=argparse.ArgumentParser()
    for k in ("oem","veci","public-key","output"):p.add_argument("--"+k,type=Path,required=True)
    for k in ("fwtool","ucert","usign"):p.add_argument("--"+k,required=True)
    a=p.parse_args()
    result=run(read(a.oem,MTD3_LIMIT),read(a.veci,MTD3_LIMIT),read(a.public_key,4096),a.fwtool,a.ucert,a.usign)
    with a.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2);f.write("\n")
    print("OFFLINE_BUNDLE=PASS; REAL_CRYPTO=PASS; FORMAT_MODELS=4; FLASH_AUTHORIZED=NO")
if __name__=="__main__":main()
