#!/usr/bin/env python3
"""J9B offline, signature-first feed audit. Operates ONLY on disposable CI files."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from j9_offline_audit import IMAGE, APPS, INDEXES

def invoke(args, timeout=90):
    try:
        p = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
        return {"ok":p.returncode == 0, "exit":p.returncode, "message":" | ".join((p.stderr or p.stdout).splitlines()[-3:])[:400]}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok":False, "exit":-1, "message":type(e).__name__}

def squashfs_offset(image):
    data = Path(image).read_bytes()
    offsets = [m.start() for m in re.finditer(b"hsqs",data)]
    if len(offsets)!=1:
        raise ValueError("Ambiguous or absent SquashFS header")
    return offsets[0]

def check_group(results):
    if not results:
        return "NOT_TESTED"
    return "PASS" if all(r["ok"] for r in results) else "BLOCKED"

def audit(firmware,feed,apk,run_id,unsquashfs="/usr/bin/unsquashfs"):
    firmware,feed,apk=Path(firmware).resolve(),Path(feed).resolve(),Path(apk).resolve()
    if not re.fullmatch(r"[0-9]{6,15}",str(run_id)):
        raise ValueError("Invalid J8c run identifier")
    image=firmware/IMAGE
    if not image.is_file() or not apk.is_file() or not Path(unsquashfs).is_file():
        raise ValueError("Required image, apk verifier, or SquashFS reader unavailable")
    selected=[feed/x for x in INDEXES]
    for name in ("veci-app-"+n for n in APPS):
        candidates=[p for p in feed.rglob("*.apk") if p.name.startswith(name+"-")]
        if len(candidates)!=1:
            raise ValueError("Missing/duplicate app: "+name)
        selected+=candidates
    for name in ("kmod-wireguard","kmod-sched-cake"):
        candidates=[p for p in feed.rglob("*.apk") if p.name.startswith(name+"-")]
        if len(candidates)!=1:
            raise ValueError("Missing/duplicate kmod: "+name)
        selected+=candidates
    if any(not p.is_file() for p in selected):
        raise ValueError("One or more requested APK indexes are absent")
    result={"j9b":"EXECUTED","j8c_run_id":str(run_id),"release_decision":"NO_GO",
            "signature":"NOT_TESTED","solver":"NOT_TESTED","metadata":"NOT_TESTED",
            "keys":"NOT_TESTED","detail":{}}
    with tempfile.TemporaryDirectory(prefix="j9b-ci-") as scratch:
        root=Path(scratch)/"root"
        extracted=invoke([unsquashfs,"-quiet","-o",str(squashfs_offset(image)),
                          "-d",str(root),str(image),"etc/apk","lib/apk"],150)
        result["detail"]["squashfs"]=extracted
        if not extracted["ok"]:
            result["keys"]="BLOCKED"
            return result
        keydir=root/"etc/apk/keys"
        keys=list(keydir.glob("*")) if keydir.is_dir() else []
        keys=[p for p in keys if p.is_file() and p.stat().st_size>0]
        result["detail"]["firmware_key_count"]=len(keys)
        result["detail"]["firmware_key_extensions"] = sorted(set(x.suffix for x in keys))
        result["keys"]="PASS" if keys else "BLOCKED"
        metadata=[invoke([apk,"adbdump","--format","json",p],20) for p in selected]
        result["metadata"]=check_group(metadata)
        result["detail"]["metadata_valid"]=sum(x["ok"] for x in metadata)
        if keys:
            signatures=[invoke([apk,"--root",root,"--keys-dir","/etc/apk/keys","verify",p],20) for p in selected]
            result["signature"]=check_group(signatures)
            result["detail"]["signatures_valid"]=sum(x["ok"] for x in signatures)
            result["detail"]["signature_tested"]=len(signatures)
            result["detail"]["signature_failure_examples"]=[x["message"] for x in signatures if not x["ok"]][:3]
            # Independent verification with the EXACT SAME extracted public keys.
            # This distinguishes CLI root-path resolution from a genuinely
            # untrusted/unsigned APKv3 artifact without granting new trust.
            direct=[invoke([apk,"--keys-dir",keydir,"verify",p],20) for p in selected]
            result["detail"]["signature_explicit_keys"] = check_group(direct)
            result["detail"]["explicit_keys_valid"] = sum(x["ok"] for x in direct)
            result["detail"]["explicit_keys_failure_examples"] = [x["message"] for x in direct if not x["ok"]][:3]
        if result["signature"]!="PASS" or result["metadata"]!="PASS":
            result["detail"]["solver_note"]="Blocked by missing firmware trust key, signature, or APKv3 metadata validation"
            return result
        # All writes below are confined to the extracted disposable image tree.
        shutil.copytree(feed,root/"j9b-feed")
        repo_file=root/"etc/apk/j9b.list"
        repo_file.parent.mkdir(parents=True,exist_ok=True)
        repo_file.write_text("".join("file:///j9b-feed/"+n+"\n" for n in INDEXES))
        simulations=[]
        for name in APPS:
            simulations.append(invoke([apk,"--root",root,"--keys-dir","/etc/apk/keys",
                "--repositories-file","/etc/apk/j9b.list","--network=false",
                "--simulate","add","--initdb","veci-app-"+name],75))
        result["solver"]=check_group(simulations)
        result["detail"]["solver_passed"]=sum(x["ok"] for x in simulations)
        result["detail"]["solver_failure_examples"]=[x["message"] for x in simulations if not x["ok"]][:3]
        return result

def main():
    p=argparse.ArgumentParser()
    for name in ("firmware","feed","apk","run-id"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--report",default="j9b-report.json")
    a=p.parse_args()
    try:
        report=audit(a.firmware,a.feed,a.apk,a.run_id)
    except (OSError,ValueError) as e:
        report={"j9b":"AUDIT_ERROR","release_decision":"NO_GO","error":str(e)}
    Path(a.report).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report["j9b"]=="EXECUTED" else 2

if __name__=="__main__":
    sys.exit(main())
