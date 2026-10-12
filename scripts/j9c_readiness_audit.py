#!/usr/bin/env python3
"""J9C static UAT readiness gate: no router access or mutations."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
APPS=("guest","sqm","ddns","wireguard","voucher")
GATES=("auth","luci_fallback","lan_wifi","lte","imei","guest","sqm","ddns",
       "wireguard","voucher","app_lifecycle","firmware_upload","firmware_signature",
       "firmware_apply","recovery","resources")
def method(src,name):
    m=re.search(r"(?ms)^"+re.escape(name)+r"\(\) \{\n(.*?)^\}",src)
    if not m: raise ValueError("Missing function "+name)
    return m.group(1)
def findings(src):
    guest=method(src["guest"],"enable_portal")
    voucher=method(src["voucher"],"method_status")
    wg=method(src["wireguard"],"method_create")
    apply=method(src["core"],"method_firmware_apply")
    validate=method(src["core"],"method_firmware_validate")
    action=method(src["core"],"method_app_action")
    return {
       "guest_partial_activation_rollback":"BLOCKED" if
          "provision_base || return 1" in guest and "wifi reload" in guest
          and "disable_portal" not in guest else "REVIEW_REQUIRED",
       "voucher_read_side_effect":"BLOCKED" if "cleanup_expired" in voucher else "REVIEW_REQUIRED",
       "wireguard_peer_auto_routes":"BLOCKED" if "route_allowed_ips=1" in wg else "REVIEW_REQUIRED",
       "updater_token_expiry":"BLOCKED" if "validation_token" in apply
          and not re.search(r"validation_(created|expires)|token_(issued|expires)|max_age",apply+validate)
          else "REVIEW_REQUIRED",
       "app_cleanup_empty_response":"BLOCKED" if 'if [ -n "$cleanup" ]; then' in action else "REVIEW_REQUIRED"
    }
def audit(root,core):
    p={a:root/("source/veci-app-"+a+"/files/usr/libexec/rpcd/veci.app."+a) for a in APPS}
    p["updater"]=root/"source/veci-update-we5927/files/usr/sbin/veci-update-agent"
    p["core"]=core/"files/rpcd-veci"
    source={k:v.read_text() for k,v in p.items()}
    syntax={}
    for name,path in p.items():
        result=subprocess.run(["sh","-n",str(path)],capture_output=True,text=True)
        syntax[name]="PASS" if result.returncode==0 else "FAIL"
    catalog={}
    lifecycle={}
    for a in APPS:
        path=root/("source/veci-app-catalog-we5927/files/usr/share/veci/apps/"+a+".json")
        info=json.loads(path.read_text())
        catalog[a]="PASS" if info.get("id")==a and info.get("packages")==["veci-app-"+a] and info.get("module")=="/veci-apps/"+a+".js" else "FAIL"
        mk=(root/("source/veci-app-"+a+"/Makefile")).read_text()
        lifecycle[a]="PASS" if "PKG_NAME:=veci-app-"+a in mk and "DEPENDS:=" in mk and "/prerm" in mk and "method_cleanup" in source[a] else "FAIL"
    pin=(root/"source/veci.commit").read_text().strip()
    pin_valid=bool(re.fullmatch("[0-9a-f]{40}",pin))
    base=pin_valid and all(z=="PASS" for d in (syntax,catalog,lifecycle) for z in d.values())
    return {
      "stage":"J9C",
      "source_readiness":"PASS" if base else "FAIL",
      "product_readiness":"BLOCKED",
      "flash_decision":"NO_GO",
      "veci_commit":pin,
      "j8c_artifact_run":"37913407078",
      "checks":{"syntax":syntax,"catalog":catalog,"lifecycle":lifecycle,"pin":pin_valid},
      "findings":findings(source),
      "hardware_uat":{g:"NOT_TESTED" for g in GATES},
      "notice":"No live router touched. Runtime source changes require new paired J8c-equivalent firmware and feed build; rerun J9/J9B."
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--veci-source",required=True)
    p.add_argument("--output",default="j9c-readiness.json")
    a=p.parse_args()
    try:
        r=audit(Path(a.root).resolve(),Path(a.veci_source).resolve())
    except (OSError,ValueError,json.JSONDecodeError) as e:
        r={"stage":"J9C","source_readiness":"FAIL","product_readiness":"BLOCKED","flash_decision":"NO_GO","error":str(e)}
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print(json.dumps(r,indent=2,sort_keys=True))
    return 0 if r["source_readiness"]=="PASS" and r["flash_decision"]=="NO_GO" else 1
if __name__=="__main__": sys.exit(main())
