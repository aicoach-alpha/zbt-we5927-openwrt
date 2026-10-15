#!/usr/bin/env python3
"""Focused real-shell tests for the fail-closed profile/MSISDN identity check."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE=Path("source/veci-telco-indonesia/files/usr/libexec/veci-xl-profile-identity-check").read_text()
MOCK='''#!/usr/bin/env python3
import json,sys
p=sys.argv
data=json.loads(open(p[p.index("-i")+1]).read())
for part in p[p.index("-e")+1][2:].split("."):
    if not isinstance(data,dict) or part not in data:
        sys.exit(1)
    data=data[part]
if data is None:
    print("null")
elif isinstance(data,str):
    print(data)
else:
    print(json.dumps(data))
'''
def run(label,profile,allow=False,symlink=False,wrong_permission=False):
    with tempfile.TemporaryDirectory(prefix="veci-profile-case-") as tmp:
        root=Path(tmp); priv=root/"private"; priv.mkdir(mode=0o700)
        pending=priv/"pending-profile"; pending.mkdir(mode=0o700)
        number=pending/"requested_number";number.write_text("6281234567890\n");number.chmod(0o600)
        file=priv/"profile-verified-transport.json"
        file.write_text(json.dumps(profile,separators=(",",":")))
        file.chmod(0o644 if wrong_permission else 0o600)
        if symlink:
            target=priv/"response.json";file.rename(target);file.symlink_to(target)
        jf=root/"jsonfilter";jf.write_text(MOCK);jf.chmod(0o755)
        work=root/"identity.sh"
        script=(SOURCE
            .replace("PENDING=/tmp/veci-telco-private/pending-profile",f"PENDING={pending}")
            .replace("PROFILE=/tmp/veci-telco-private/profile-verified-transport.json",f"PROFILE={file}")
            .replace("dir_ok /tmp/veci-telco-private",f"dir_ok {priv}")
            .replace("JSONFILTER=/usr/bin/jsonfilter",f"JSONFILTER={jf}"))
        work.write_text(script)
        subprocess.run(["sh","-n",str(work)],check=True)
        p=subprocess.run(["sh",str(work),"--check"],text=True,capture_output=True)
        assert not p.stderr,(label,p.stderr)
        assert "6281234567890" not in p.stdout
        if allow:
            assert p.returncode==0,(label,p.stdout)
            assert "VECI_XL_PROFILE_NUMBER_MATCH=pass" in p.stdout
            assert "VECI_XL_PROFILE_ACCOUNT_PROMOTED=false" in p.stdout
            assert "VECI_XL_QUOTA_TRUST=not_authenticated" in p.stdout
        else:
            assert p.returncode!=0,(label,p.stdout)
            assert "VECI_XL_PROFILE=blocked" in p.stdout
            assert "VECI_XL_PROFILE_NUMBER_MATCH=pass" not in p.stdout
        assert not (priv/"id_token").exists()
        assert not (priv/"quota-xl.json").exists()
        print("VECI_XL_PROFILE_CASE=pass",label)

if __name__=="__main__":
    if os.geteuid()!=0:
        raise SystemExit("root needed to exercise the root-only gate")
    run("exact_msisdn",{"status":"SUCCESS","data":{"msisdn":"6281234567890"}},True)
    run("local_08_number",{"status":"SUCCESS","data":{"mobile_number":"081234567890"}},True)
    run("subscriber_id_not_number",{"status":"SUCCESS","data":{"subscriber_id":"a1b2c3"}})
    run("different_account",{"status":"SUCCESS","data":{"msisdn":"6289876543210"}})
    run("conflicting_identity",{"status":"SUCCESS","data":{"msisdn":"6281234567890","mobile_number":"6289876543210"}})
    run("operator_failure",{"status":"FAILED","data":{"msisdn":"6281234567890"}})
    run("unsafe_symlink",{"status":"SUCCESS","data":{"msisdn":"6281234567890"}},symlink=True)
    run("unsafe_mode",{"status":"SUCCESS","data":{"msisdn":"6281234567890"}},wrong_permission=True)
    assert "carrier_authenticated" not in SOURCE
    assert "token_candidate.json" not in SOURCE
    assert "subscriber_id" in SOURCE
    assert "VECI_XL_QUOTA_TRUST=not_authenticated" in SOURCE
    print("VECI_XL_PROFILE_FOCUSED=pass")
