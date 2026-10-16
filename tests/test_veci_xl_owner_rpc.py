#!/usr/bin/env python3
"""Only exercise actual XL owner RPC HTTPS/credential gates, no network."""
import json
import os
import pathlib
import subprocess
import tempfile

BASE=pathlib.Path("source/veci-telco-xl-native/files")
RPC=(BASE/"usr/libexec/rpcd/veci.xl").read_text()
PAGE=(BASE/"www/veci/xl-account.html").read_text()
UI=(BASE/"www/veci/xl-account.js").read_text()
ACL=json.loads((BASE/"usr/share/rpcd/acl.d/veci-xl-owner.json").read_text())

def run_case(https, method):
    with tempfile.TemporaryDirectory(prefix="veci-xl-gate-") as tmp:
        p=pathlib.Path(tmp)
        ciam=p/"ciam"
        priv=p/"private"
        mock=p/"bin"
        mock.mkdir()
        cert=p/"cert.pem"
        key=p/"key.pem"
        cert.write_text("test fixture")
        key.write_text("test fixture")
        uci=mock/"uci"
        uci.write_text(f"""#!/bin/sh
case "$4" in
  uhttpd.main.listen_http) {"printf '0.0.0.0:80\\n'" if not https else ":"} ;;
  uhttpd.main.listen_https) printf '0.0.0.0:443\\n' ;;
  uhttpd.main.cert) printf '%s\\n' '{cert}' ;;
  uhttpd.main.key) printf '%s\\n' '{key}' ;;
esac
""")
        # uci -q get value has three args, not four
        uci.write_text(uci.read_text().replace('case "$4" in','case "$3" in'))
        uci.chmod(0o755)
        source=RPC.replace("CIAM=/tmp/veci-xl-ciam",f"CIAM={ciam}") .replace("PRIVATE=/tmp/veci-telco-private",f"PRIVATE={priv}") .replace("LOCK=/tmp/veci-xl-owner-rpc.lock",f"LOCK={p/'lock'}") .replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin",f"PATH={mock}:/usr/sbin:/usr/bin:/sbin:/bin")
        job=p/"veci-xl-rpc"
        job.write_text(source)
        subprocess.run(["sh","-n",str(job)],check=True)
        env=dict(os.environ)
        env["PATH"]=str(mock)+":"+env.get("PATH","")
        r=subprocess.run(["sh",str(job),"call",method],
                         input='{"number":"6281234567890"}',capture_output=True,text=True,env=env)
        assert r.returncode==0,(r.stdout,r.stderr)
        data=json.loads(r.stdout)
        assert "6281234567890" not in r.stdout+r.stderr
        if method=="status":
            assert data["https_only"] is https
            assert data["operator_configured"] is False
            assert data["session"]=="not_connected"
        else:
            assert data["reason"]==("operator_config_unavailable" if https else "https_only_required"),data
        assert not ciam.exists() and not priv.exists()
        print("VECI_XL_OWNER_GATE_CASE=pass",f"{method}_{'https' if https else 'http'}")

def main():
    for mode in (False,True):
        run_case(mode,"status")
        run_case(mode,"requestOtp")
    read=ACL["veci-xl-owner"]["read"]["ubus"]["veci.xl"]
    write=ACL["veci-xl-owner"]["write"]["ubus"]["veci.xl"]
    assert read==["status"]
    assert set(write)=={"requestOtp","submitOtp","refreshQuota"}
    assert 'https_only_required' in RPC
    assert 'otp_cooldown' in RPC
    assert 'ubus call' not in RPC
    assert 'AT+CMGR' not in RPC and 'AT+CUSD' not in RPC
    assert "https:" in UI and "sessionId" in UI
    assert "sessionStorage" not in UI and "localStorage" not in UI
    assert "console." not in UI
    assert "Content-Security-Policy" in PAGE
    assert "form-action 'none'" in PAGE and "connect-src 'self'" in PAGE
    assert 'type="password"' in PAGE
    # HTTPS has a separate session origin from the HTTP VeCI dashboard.
    # The XL page must be able to authenticate directly in the same tab,
    # not ask the user to reopen it with an unavailable existing session.
    for field in ('xl-veci-signin','xl-veci-user','xl-veci-password',
                  'xl-veci-signin-button'):
        assert f'id="{field}"' in PAGE,field
    assert "await api.login(username, password)" in UI
    assert "await api.validateSession()" in UI
    assert "if (!secure())" in UI
    assert "'xl-veci-password'" in UI
    assert "passwordField.value = ''" in UI
    assert "signin.hidden = true" in UI
    assert "sign in to VeCI first, then reopen" not in UI.lower()
    assert 'src="./xl-account.js"' in PAGE
    assert 'href="/veci/#/cellular"' in PAGE
    pkg=pathlib.Path("source/veci-telco-xl-native/Makefile").read_text()
    for expected in ("PKG_VERSION:=0.3.7","veci.xl","veci-xl-owner.json","xl-account.html","xl-account.js"):
        assert expected in pkg,expected
    print("VECI_XL_OWNER_AUTH_AND_UI_FOCUSED=pass")

if __name__=="__main__":
    main()
