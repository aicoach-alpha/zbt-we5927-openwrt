#!/usr/bin/env python3
"""Source-only acceptance of native VeCI login/RPC permissions and SSH/HTTPS.

Only promotes two specified modules after module-scoped tests actually pass.
Hashes code, source tests, fixtures, and the raw command output. No build.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
OUT=ROOT/"docs/source-acceptance"
RT="rebuild/veci-v2/packages/veci-v2-runtime/"
UI="rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/"
SPECS={
 "router_login_and_permissions":{
    "implementation_files":[UI+"app.js",UI+"index.html",RT+"veci2-status-acl.json"],
    "test_source_files":[
        "scripts/tests/test_owner_auth_acceptance.py",
        "scripts/tests/test_veci_ui_sessions.py",
        "scripts/tests/fixtures/veci_ui_sessions.js"
    ],
    "test_patterns":["test_owner_auth_acceptance.py","test_veci_ui_sessions.py"],
    "test_ids":[
        "test_real_login_logout_session_state_machine",
        "test_session_token_scope_and_no_credential_persistence",
        "test_read_only_acl_and_write_scopes_are_separated",
        "test_rpc_uses_token_with_server_side_permission_checks",
        "test_login_permissions_and_logout",
        "test_runtime_read_role_grants_only_self_logout_and_diagnostics"
    ]
 },
 "system_access_ssh_https":{
    "implementation_files":[
        RT+"veci2-access",RT+"veci2-access-acl.json",UI+"access.js",
        UI+"index.html","rebuild/veci-v2/packages/veci-v2-runtime/Makefile",
        "rebuild/veci-v2/packages/veci-v2-ui/Makefile"
    ],
    "test_source_files":[
        "scripts/tests/test_owner_access_acceptance.py",
        "scripts/tests/fixtures/uci_access_sandbox.py",
        "scripts/uat/test-access-host.py"
    ],
    "test_patterns":["test_owner_access_acceptance.py"],
    "test_ids":[
        "test_original_uat_with_isolated_config_and_complete_crud",
        "test_access_rpc_writes_only_config_without_restarting_network"
    ]
 }
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data=json.loads(CONTRACT.read_text())
    modules={item["id"]:item for item in data["required_core"]}
    preexisting=json.loads(EVIDENCE.read_text())
    if len(data["required_core"])!=40 or any(name not in modules for name in SPECS):
        raise ValueError("Cannot change incomplete or mismatched core list")
    results={}
    OUT.mkdir(exist_ok=True,parents=True)
    for name,spec in SPECS.items():
        if modules[name]["v2_state"] not in ("not_ported_to_v2","source_verified"):
            raise ValueError("unexpected module status: "+name)
        if modules[name].get("physical_uat")!="not_run":
            raise ValueError("physical state unexpectedly changed")
        files=spec["implementation_files"]+spec["test_source_files"]
        if not all((ROOT/f).is_file() for f in files):
            raise ValueError("missing source inputs: "+name)
        records=[]
        for pattern in spec["test_patterns"]:
            cmd=["python3","-m","unittest","discover",
                 "-s",str(ROOT/"scripts/tests"),"-p",pattern,"-v"]
            run=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=90,
                               env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
            report=run.stdout+"\n"+run.stderr
            if run.returncode!=0 or "\nOK\n" not in report or "Ran " not in report:
                print("SOURCE_ACCEPTANCE_FAILED",name,pattern,report[-5000:],file=sys.stderr)
                raise SystemExit(5)
            records.append("$ "+" ".join(cmd)+"\n"+report)
        all_output="\n".join(records)
        for method in spec["test_ids"]:
            if method not in all_output:
                raise ValueError("required named test not actually executed: "+method)
        log=OUT/(name+".txt")
        log.write_text(all_output)
        results[name]={
            "status":"pass",
            "scope":"source_verified_no_hardware_uat",
            "implementation_files":spec["implementation_files"],
            "test_source_files":spec["test_source_files"],
            "test_ids":spec["test_ids"],
            "source_sha256":{f:digest(ROOT/f) for f in files},
            "receipt":{
                "kind":"executed_source_tests",
                "exit_code":0,
                "hardware_uat":"not_run",
                "log_file":log.relative_to(ROOT).as_posix(),
                "log_sha256":digest(log),
                "executed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds")
            }
        }
        print("SOURCE_ACCEPTANCE",name,"TESTS",len(spec["test_ids"]),
              "RECEIPT_SHA256",digest(log))
    for name in SPECS:
        modules[name]["v2_state"]="source_verified"
    preexisting.setdefault("modules",{}).update(results)
    EVIDENCE.write_text(json.dumps(preexisting,indent=2,sort_keys=True)+"\n")
    CONTRACT.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")


if __name__=="__main__":
    main()
