#!/usr/bin/env python3
"""Shared offline format + synthetic NOR model; no flash authorization.

Both stages consume one immutable byte snapshot. This is not U-Boot
emulation, signature verification, or runtime OTA integration.
"""
import argparse
import json
from pathlib import Path
from we5927_recovery_image_format_gate_20261127 import (
    analyze_bytes, FormatGateError, MTD3_LIMIT, VENDOR_SHA, VECI_SHA)
from we5927_recovery_nor_model_20261128 import simulate

ROLES={
    "oem_reference":(VENDOR_SHA,"OEM_STYLE_DEADC0DE_TERMINATOR"),
    "signed_veci_candidate":(VECI_SHA,"OPENWRT_METADATA_SIGNATURE_TRAILER"),
}

def evaluate(image,role,expected_sha):
    if role not in ROLES:
        raise FormatGateError("UNKNOWN_RESEARCH_ROLE")
    if not isinstance(image,bytes):
        raise FormatGateError("IMMUTABLE_BYTES_REQUIRED")
    report=analyze_bytes(image,expected_sha)
    if report["trailer"]["class"]!=ROLES[role][1]:
        raise FormatGateError("ROLE_TRAILER_MISMATCH")
    models=[simulate(image,erase_policy=p) for p in ("rounded_payload","whole_firmware")]
    return {"schema":"we5927-offline-shared-recovery-model.v1",
            "role":role,"format":report,"models":models,
            "format_and_model_status":"PASS",
            "actual_signature_verification":"NOT_PERFORMED_BY_THIS_TOOL",
            "bootloader_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--role",choices=ROLES,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    with a.image.open("rb") as f:
        image=f.read(MTD3_LIMIT+1)
    report=evaluate(image,a.role,ROLES[a.role][0])
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2);f.write("\n")
    print("ROLE="+a.role+"; FORMAT_AND_MODEL=PASS; MODELS=2; FLASH_AUTHORIZED=NO")
if __name__=="__main__":
    main()
