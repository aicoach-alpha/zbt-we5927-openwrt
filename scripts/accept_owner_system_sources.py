#!/usr/bin/env python3
"""Re-run exact source tests and issue hashed receipts for two VeCI modules.
No firmware build, no router access, no hardware UAT assertions.
"""
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE=ROOT/"rebuild/veci-v2/contracts/owner-final-source-evidence.json"
OUT=ROOT/"docs/source-acceptance"
RT="rebuild/veci-v2/packages/veci-v2-runtime/"
UI="rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/"
SPECS={
 "system_services_startup":{
  "implementation_files":[RT+"veci2-services",RT+"veci2-services-acl.json",UI+"services.js"],
  "test_source_files":["scripts/tests/test_owner_services_acceptance.py"],
  "test_ids":["test_real_provider_lifecycle_in_sandbox","test_no_unrestricted_lte_network_or_ssh_boot_changes"]
 },
 "system_time_ntp":{
  "implementation_files":[RT+"veci2-system-admin",RT+"veci2-status-acl.json"],
  "test_source_files":["scripts/tests/test_owner_ntp_acceptance.py"],
  "test_ids":["test_real_rpc_ntp_staging_and_rollback","test_uci_acl_and_no_radio_lte_modification"]
 }
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 results={}
 for name,scope in SPECS.items():
  all_files=scope["implementation_files"]+scope["test_source_files"]
  assert all((ROOT/x).is_file() for x in all_files)
  logs=[]
  for src in scope["test_source_files"]:
   cmd=["python3","-m","unittest","discover","-s",str(ROOT/"scripts/tests"),"-p",Path(src).name,"-v"]
   run=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=75,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
   output=run.stdout+"\n"+run.stderr
   if run.returncode or "\nOK\n" not in output or "Ran " not in output:
    print("SOURCE ACCEPTANCE FAILED",name,output[-4500:],file=sys.stderr)
    raise SystemExit(4)
   if not all(method in output for method in scope["test_ids"]):
    raise ValueError("Acceptance receipt lacks required executed test")
   logs.append("$ "+" ".join(cmd)+"\n"+output)
  log=OUT/(name+".txt")
  log.write_text("\n".join(logs))
  results[name]={
   "status":"pass",
   "scope":"source_verified_no_hardware_uat",
   "implementation_files":scope["implementation_files"],
   "test_source_files":scope["test_source_files"],
   "test_ids":scope["test_ids"],
   "source_sha256":{x:sha(ROOT/x) for x in all_files},
   "receipt":{"kind":"executed_source_tests","exit_code":0,
              "hardware_uat":"not_run","log_file":log.relative_to(ROOT).as_posix(),
              "log_sha256":sha(log),"executed_utc":datetime.now(timezone.utc).isoformat(timespec="seconds")}
  }
  print("ACCEPTED_SOURCE_ONLY",name,"methods",len(scope["test_ids"]),"LOG_SHA256",sha(log))
 contract=json.loads(CONTRACT.read_text())
 evidence=json.loads(EVIDENCE.read_text())
 for item in contract["required_core"]:
  if item["id"] in results:
   assert item["v2_state"]=="not_ported_to_v2" and item["physical_uat"]=="not_run"
   item["v2_state"]="source_verified"
 assert len(results)==2
 evidence["modules"].update(results)
 EVIDENCE.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
 CONTRACT.write_text(json.dumps(contract,sort_keys=True,indent=2)+"\n")
if __name__=="__main__": main()
