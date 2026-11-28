#!/usr/bin/env python3
"""Audit exact Git source snapshots for shared verifier parity, not runtime UAT."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CORE="rebuild/veci-v2/packages/veci-v2-runtime/veci2-verify-image"
POLICY="rebuild/veci-v2/packages/veci-v2-runtime/update-policy.default"
CGI="rebuild/veci-v2/packages/veci-v2-ui/files/www/cgi-bin/veci2-verify"
ADAPTER="rebuild/oem-updated/backend/verify-only.sh"
STAGER="rebuild/oem-updated/stage_variant.py"
MANIFEST="rebuild/oem-updated/shared-backend.json"
REBOOT_GUARD=b"""[ ! -e /var/run/veci2-reboot-requested ] && [ ! -L /var/run/veci2-reboot-requested ] || reply '409 Conflict' '{"error":"reboot_pending"}'\n"""

def sha(b):return hashlib.sha256(b).hexdigest()

def audit(veci,oem):
    errors=[]
    if veci[CORE]!=oem[CORE]:errors.append("CORE_VERIFIER_DIVERGED")
    if veci[POLICY].strip()!=b"verify_only" or oem[POLICY].strip()!=b"verify_only":
        errors.append("DEFAULT_NOT_VERIFY_ONLY")
    if oem[CGI]==veci[CGI]:
        cgi_relation="IDENTICAL"
    elif oem[CGI].count(REBOOT_GUARD)==1 and oem[CGI].replace(REBOOT_GUARD,b"")==veci[CGI]:
        cgi_relation="OEM_ADDS_REBOOT_INTERLOCK"
    else:
        cgi_relation="UNREVIEWED_DIVERGENCE";errors.append("CGI_DIVERGED")
    # These are source-shape checks, not a general shell semantics analyzer.
    if b'[ "${QUERY_STRING:-}" = "" ] || {' not in oem[ADAPTER] or b"403 Forbidden" not in oem[ADAPTER] or b"exec /usr/libexec/oem-updated/shared-verify" not in oem[ADAPTER]:
        errors.append("OEM_VERIFY_ONLY_WRAPPER_SHAPE_CHANGED")
    if b'shutil.copyfile(shared / "cgi-bin/veci2-verify", verify)' not in oem[STAGER] or b'shutil.copyfile(HERE / "backend/verify-only.sh", verify_gate)' not in oem[STAGER]:
        errors.append("OEM_STAGING_SHAPE_CHANGED")
    manifest=json.loads(oem[MANIFEST])
    for path in (CORE,POLICY,CGI):
        if manifest.get("files",{}).get(path)!=sha(oem[path]):errors.append("OEM_MANIFEST_MISMATCH:"+path)
    return {"schema":"we5927-cross-variant-verifier-source.v1","core_identical":veci[CORE]==oem[CORE],
            "core_sha256":sha(veci[CORE]),"cgi_relation":cgi_relation,
            "veci_cgi_sha256":sha(veci[CGI]),"oem_cgi_sha256":sha(oem[CGI]),
            "errors":errors,"source_audit":"PASS" if not errors else "FAIL",
            "runtime_acceptance":"NOT_TESTED","flash_authorized":False,"release_permitted":False}

def load(repo,ref,paths):
    if re.fullmatch(r"[0-9a-f]{40}",ref) is None:raise ValueError("EXACT_COMMIT_REQUIRED")
    return {p:subprocess.check_output(["git","-C",str(repo),"show",ref+":"+p],timeout=15) for p in paths}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--veci-commit",required=True);p.add_argument("--oem-commit",required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    r=audit(load(a.repo,a.veci_commit,(CORE,POLICY,CGI)),load(a.repo,a.oem_commit,(CORE,POLICY,CGI,ADAPTER,STAGER,MANIFEST)))
    r.update(veci_commit=a.veci_commit,oem_commit=a.oem_commit)
    with a.output.open("x",encoding="utf-8") as f:json.dump(r,f,indent=2);f.write("\n")
    print("CROSS_VARIANT_SOURCE="+r["source_audit"]+"; CGI="+r["cgi_relation"]+"; FLASH_AUTHORIZED=NO")
    return 0 if not r["errors"] else 3
if __name__=="__main__":raise SystemExit(main())
