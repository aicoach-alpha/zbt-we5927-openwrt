#!/usr/bin/env python3
"""Re-run real source+PTY tests before granting TWO module source acceptance.

This never writes router state, builds an image, or treats fake modem UAT as
physical UAT. Generates code/test SHA256 receipts and updates exactly two
specific source contract rows after successfully executed tests.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
OUT=ROOT/"docs/source-acceptance"
SPECS={
 "lte_apn_pin_puk":{
  "source_files":[
    "rebuild/veci-v2/packages/veci-v2-runtime/veci2-lte-policy",
    "rebuild/veci-v2/packages/veci-v2-runtime/veci2-sim-lock",
    "source/we5927-lte/files/usr/sbin/we5927-lte",
    "source/we5927-lte/src/we5927-at.c",
    "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/sim-lock.js"
  ],
  "test_source_files":["scripts/tests/test_owner_apn_acceptance.py","scripts/tests/test_sim_unlock.py"],
  "test_ids":["test_actual_oem_apn_validator",
    "test_real_rpc_provider_uci_staging_and_no_modem_restart",
    "test_private_sim_and_apn_acl_and_board_safety","test_guarded_transport"],
  "test_patterns":["test_owner_apn_acceptance.py","test_sim_unlock.py"]
 },
 "lte_ussd":{
  "source_files":[
    "rebuild/veci-v2/packages/veci-v2-runtime/veci2-ussd",
    "source/we5927-lte/src/we5927-at.c",
    "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/ussd.js"
  ],
  "test_source_files":["scripts/tests/test_owner_ussd_acceptance.py"],
  "test_ids":["test_pty_fake_modem_one_shot_timeout_cancel_and_rejects",
    "test_at_helper_rejects_input_injection_without_opening_modem",
    "test_rpc_is_scoped_and_fails_closed"],
  "test_patterns":["test_owner_ussd_acceptance.py"]
 }
}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify():
    outcome={}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,spec in SPECS.items():
        log=OUT/(name+".txt")
        segments=[]
        for pattern in spec["test_patterns"]:
            cmd=["python3","-m","unittest","discover","-s",str(ROOT/"scripts/tests"),"-p",pattern,"-v"]
            p=subprocess.run(cmd,cwd=ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},
                text=True,capture_output=True,timeout=75)
            output=p.stdout+"\n"+p.stderr
            segments.append("$ "+" ".join(cmd)+"\n"+output)
            if p.returncode!=0 or "\nOK\n" not in output or "Ran " not in output:
                print("SOURCE_ACCEPTANCE_FAILED",name,pattern,file=sys.stderr)
                print(output[-4000:],file=sys.stderr)
                raise SystemExit(5)
        log.write_text("\n".join(segments))
        rel="docs/source-acceptance/"+log.name
        files=spec["source_files"]+spec["test_source_files"]
        assert all((ROOT/x).is_file() for x in files)
        outcome[name]={
          "status":"pass",
          "scope":"source_verified_no_hardware_uat",
          "implementation_files":spec["source_files"],
          "test_source_files":spec["test_source_files"],
          "test_ids":spec["test_ids"],
          "source_sha256":{x:digest(ROOT/x) for x in files},
          "receipt":{
            "kind":"executed_source_tests",
            "exit_code":0,
            "hardware_uat":"not_run",
            "log_file":rel,
            "log_sha256":digest(log),
            "executed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds")
          }
        }
        print("ACCEPTED_SOURCE_ONLY",name,"methods",len(spec["test_ids"]),"log-sha256",digest(log))
    contract=json.loads(CONTRACT.read_text())
    for item in contract["required_core"]:
        if item["id"] in outcome:
            assert item["physical_uat"]=="not_run"
            assert item["v2_state"] in ("not_ported_to_v2","source_verified")
            item["v2_state"]="source_verified"
    existing=json.loads(EVIDENCE.read_text()) if EVIDENCE.is_file() else {"modules":{}}
    existing.setdefault("modules",{}).update(outcome)
    EVIDENCE.write_text(json.dumps(existing,sort_keys=True,indent=2)+"\n")
    CONTRACT.write_text(json.dumps(contract,sort_keys=True,indent=2)+"\n")
if __name__=="__main__":verify()
