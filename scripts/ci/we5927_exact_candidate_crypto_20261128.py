#!/usr/bin/env python3
"""Exact signed candidate verification with pinned public key; no flash approval."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_veci_image import verify, GateError
from we5927_recovery_image_format_gate_20261127 import VECI_SHA, MTD3_LIMIT

PUB_SHA="ac67651a0f3a55449aea44b76040329d95374e570c0690490d8ce94f2c61d220"
FINGERPRINT="1d8759d36251c36c"
UNSIGNED_SHA="8961f21d63cf28add9c01a888b3cb54b20c305f16396ff20d049acce99925506"
def sha(data):return hashlib.sha256(data).hexdigest()
def validate_inputs(image,key):
    if sha(image)!=VECI_SHA or len(image)!=5899090:
        raise GateError("EXACT_SIGNED_CANDIDATE_MISMATCH")
    if sha(key)!=PUB_SHA:
        raise GateError("PINNED_PUBLIC_KEY_MISMATCH")
def check(image,key,fwtool,ucert,usign):
    validate_inputs(image,key)
    with tempfile.TemporaryDirectory(prefix="veci-pinned-verify-") as d:
        root=Path(d); f=root/"candidate.bin"; f.write_bytes(image)
        trust=root/"trust";trust.mkdir()
        pub=trust/FINGERPRINT;pub.write_bytes(key)
        fp=subprocess.run([usign,"-F","-p",str(pub)],capture_output=True,check=True,timeout=15)
        if fp.stdout.decode().strip()!=FINGERPRINT:raise GateError("FINGERPRINT_MISMATCH")
        proof=verify(f,VECI_SHA,trust,fwtool,ucert)
        unsigned=subprocess.run([fwtool,"-T","-s","/dev/null",str(f)],capture_output=True,check=True,timeout=20)
        if sha(unsigned.stdout)!=UNSIGNED_SHA:raise GateError("SIGNED_MESSAGE_MISMATCH")
        # Extract original certificate, then tamper with the unsigned
        # message directly so fwtool trailer CRC cannot mask crypto failure.
        cert=root/"signature.ucert"
        subprocess.run([fwtool,"-s",str(cert),str(f)],capture_output=True,check=True,timeout=20)
        msg=root/"unsigned.bin";msg.write_bytes(unsigned.stdout)
        args=[ucert,"-V","-m",str(msg),"-c",str(cert),"-P",str(trust)]
        good=subprocess.run(args,capture_output=True,timeout=30)
        if good.returncode!=0:raise GateError("DIRECT_UNSIGNED_SIGNATURE_FAILED")
        bad=bytearray(unsigned.stdout);bad[128]^=1;msg.write_bytes(bad)
        rejected=subprocess.run(args,capture_output=True,timeout=30)
        if rejected.returncode==0:raise GateError("TAMPER_ACCEPTED")
        msg.write_bytes(unsigned.stdout)
        if subprocess.run(args,capture_output=True,timeout=30).returncode!=0:
            raise GateError("POSITIVE_CONTROL_AFTER_TAMPER_FAILED")
        pub.unlink()
        try:verify(f,VECI_SHA,trust,fwtool,ucert)
        except GateError as exc:
            if "contains no keys" not in str(exc):raise
        else:raise GateError("MISSING_TRUST_ACCEPTED")
    return {"schema":"we5927-exact-signed-candidate-crypto.v1",
            "image_sha256":VECI_SHA,"public_key_sha256":PUB_SHA,"fingerprint":FINGERPRINT,
            "unsigned_sha256":UNSIGNED_SHA,"metadata":"PASS",
            "signature_against_pinned_nas_public_key":"PASS","tampered_payload_crypto_rejected":True,
            "missing_trust_rejected":True,"router_current_trust_reverified":False,
            "bootloader_acceptance":"NOT_VERIFIED","physical_recovery":"NOT_TESTED",
            "flash_authorized":False,"release_permitted":False,"router_contacted":False}
def main():
    p=argparse.ArgumentParser()
    for k in ("image","public-key","output"):p.add_argument("--"+k,required=True,type=Path)
    for k in ("fwtool","ucert","usign"):p.add_argument("--"+k,required=True)
    a=p.parse_args()
    with a.image.open("rb") as f:image=f.read(MTD3_LIMIT+1)
    with a.public_key.open("rb") as f:key=f.read(4097)
    r=check(image,key,a.fwtool,a.ucert,a.usign)
    with a.output.open("x",encoding="utf-8") as f:json.dump(r,f,indent=2);f.write("\n")
    print("PINNED_SIGNATURE=PASS; TAMPER_REJECTED=PASS; MISSING_TRUST_REJECTED=PASS; FLASH_AUTHORIZED=NO")
if __name__=="__main__":main()
