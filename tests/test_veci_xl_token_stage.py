#!/usr/bin/env python3
"""Focused test for the real XL pending-token shell script, no operator I/O."""
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

SOURCE = Path("source/veci-telco-indonesia/files/usr/libexec/veci-xl-token-stage").read_text()
MOCK = """#!/usr/bin/env python3
import json,sys
args=sys.argv
path=args[args.index("-i")+1]
field=args[args.index("-e")+1][2:]
doc=json.loads(open(path).read())
value=doc.get(field)
if value is None:
    sys.exit(2)
print(value)
"""
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4bCJ9.c2lnbmF0dXJlc2VnbWVudA"
SECRET_A = "access_token_abcdefghijklmnopqrstuvwxyz0123456789"
SECRET_R = "refresh_token_abcdefghijklmnopqrstuvwxyz0123456789"

def run_case(label, doc, bad_permissions=False, symlink=False):
    with tempfile.TemporaryDirectory(prefix="veci-ciam-stage-") as tmp:
        root=Path(tmp); ciam=root/"ci"; ciam.mkdir(mode=0o700)
        target=root/"private"
        candidate=ciam/"token-candidate.json"
        candidate.write_text(json.dumps(doc))
        candidate.chmod(0o600)
        number=ciam/"number"
        number.write_text("6281234567890\n")
        number.chmod(0o600)
        if bad_permissions:
            candidate.chmod(0o644)
        if symlink:
            real=ciam/"real.json"
            candidate.rename(real)
            candidate.symlink_to(real)
        parser=root/"jsonfilter"
        parser.write_text(MOCK)
        parser.chmod(0o755)
        local_source=(SOURCE
            .replace("CIAM=/tmp/veci-xl-ciam",f"CIAM={ciam}")
            .replace("PRIVATE=/tmp/veci-telco-private",f"PRIVATE={target}")
            .replace("JSONFILTER=/usr/bin/jsonfilter",f"JSONFILTER={parser}"))
        job=root/"job.sh"
        job.write_text(local_source)
        subprocess.run(["sh","-n",str(job)],check=True)
        before=subprocess.run(["sh",str(job),"--status"],capture_output=True,text=True,check=True)
        assert "VECI_XL_STAGE=not_staged" in before.stdout
        p=subprocess.run(["sh",str(job),"--stage"],capture_output=True,text=True)
        assert not p.stderr, (label,p.stderr)
        assert JWT not in p.stdout and SECRET_A not in p.stdout and SECRET_R not in p.stdout
        if label=="valid":
            assert p.returncode==0,p.stdout
            assert "VECI_XL_STAGE=pending_profile" in p.stdout
            assert "VECI_XL_QUOTA_TRUST=not_authenticated" in p.stdout
            assert not candidate.exists()
            pending=target/"pending-profile"
            assert pending.is_dir()
            assert (pending.stat().st_mode & 0o777)==0o700
            for name,expected in [
                ("id_token",JWT),("access_token",SECRET_A),
                ("refresh_token",SECRET_R),("requested_number","6281234567890")
            ]:
                v=pending/name
                assert (v.stat().st_mode & 0o777)==0o600
                assert v.read_text().strip()==expected
            assert not (target/"id_token").exists()
            check=subprocess.run(["sh",str(job),"--status"],capture_output=True,text=True,check=True)
            assert "VECI_XL_STAGE=pending_profile" in check.stdout
            # No duplicate account staging or token overwrite.
            retry=subprocess.run(["sh",str(job),"--stage"],capture_output=True,text=True)
            assert retry.returncode!=0
        else:
            assert p.returncode!=0,(label,p.stdout)
            assert "VECI_XL_STAGE=blocked" in p.stdout
            assert not (target/"pending-profile").exists()
        print("VECI_XL_TOKEN_STAGE_CASE=pass",label)

def main():
    if os.geteuid()!=0:
        raise RuntimeError("test as root to exercise real root-only gate")
    base=dict(id_token=JWT, access_token=SECRET_A,
              refresh_token=SECRET_R,expires_in=3600)
    run_case("valid",base)
    run_case("missing_refresh",dict(id_token=JWT,access_token=SECRET_A,expires_in=3600))
    run_case("invalid_ttl",dict(base,expires_in=-5))
    run_case("weak_file_mode",base,bad_permissions=True)
    run_case("symlink_candidate",base,symlink=True)
    assert "carrier_authenticated" not in SOURCE
    assert "ubus" not in SOURCE
    assert "wget " not in SOURCE
    assert "curl " not in SOURCE
    print("VECI_XL_TOKEN_STAGE_FOCUSED=pass")

if __name__=="__main__":
    main()
