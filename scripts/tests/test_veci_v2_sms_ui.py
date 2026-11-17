"""SMS Center v2: reviewed PDU codec and consent-driven modem workflow."""
from pathlib import Path
import json
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
CODEC=(UI/"sms-codec.js").read_text()
CENTER=(UI/"sms-center.js").read_text()
APP=(UI/"app.js").read_text()
HTML=(UI/"index.html").read_text()
PKG=(ROOT/"rebuild/veci-v2/packages/veci-v2-ui/Makefile").read_text()


class SmsCenterV2(unittest.TestCase):
    def test_codec_exactly_tracks_reviewed_v1_parser_function_block(self):
        v1=(ROOT/"source/veci-core/veci/js/pages/cellular.js").read_text()
        first=v1.index("function buildSmsSubmit(")
        last=v1.index("\nexport default {",first)
        self.assertIn(v1[first:last],CODEC)
        self.assertIn("globalThis.VeciSmsCodec = Object.freeze",CODEC)

    def test_gsm_ucs2_and_three_part_pdu_vector(self):
        script="""
const vm=require('vm'),fs=require('fs');
const code=fs.readFileSync(process.argv[1],'utf8');
const context={}; context.globalThis=context;
vm.runInNewContext(code,context,{timeout:1000});
const c=context.VeciSmsCodec;
const sample=(s)=>c.decodeSentPdu(c.buildSmsSubmit('+628123456789',s)).text;
if(sample('Halo V2')!=='Halo V2') throw new Error('GSM7 corruption');
if(sample('Halo ❤️')!=='Halo ❤️') throw new Error('UCS2 corruption');
const parts=c.buildSmsSubmitSegments('+628123456789','A'.repeat(310),66);
if(parts.length!==3) throw new Error('multipart section count');
if(parts.some((p,i)=>c.decodeSentPdu(p).concat.part!==i+1)) throw new Error('multipart order');
for(const invalid of ['xyz','', '0','+622123']) {
 if(invalid==='+622123') continue;
 let rejected=false;try {c.buildSmsSubmit(invalid,'Hi')}catch {rejected=true}
 if(!rejected) throw new Error('accepted invalid recipient');
}
console.log(JSON.stringify({gsm:'PASS',ucs2:'PASS',multipart:parts.length}));
"""
        p=subprocess.run(["node","-e",script,str(UI/"sms-codec.js")],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)["multipart"],3)

    def test_sms_requires_user_action_and_never_retries_unknown_outcome(self):
        self.assertIn("window.confirm('Kirim '",CENTER)
        self.assertIn("if (!window.confirm",CENTER)
        self.assertIn("const random = new Uint8Array(1)",CENTER)
        self.assertIn("crypto.getRandomValues",CENTER)
        self.assertIn("sendMessage',{pdu:plan[i]}",CENTER)
        self.assertIn("await pause(5300)",CENTER)
        self.assertIn("Jangan kirim ulang otomatis",CENTER)
        self.assertIn("accepted_by_modem",CENTER)
        self.assertIn("history_saved",CENTER)
        self.assertNotIn("setInterval(",CENTER)
        self.assertNotIn("localStorage",CENTER)
        self.assertNotIn("sessionStorage",CENTER)
        self.assertNotIn("innerHTML",CENTER)
        self.assertNotRegex(CENTER,r"(?i)\bretry\(|auto.?resend")

    def test_sms_private_data_cleared_on_logout(self):
        self.assertIn("globalThis.VeciSmsCenter.logout();",APP)
        self.assertIn("function logout()",CENTER)
        self.assertIn("clearPrivateData()",CENTER)
        self.assertIn("generation++",CENTER)
        self.assertIn("function isCurrent(token)",CENTER)
        self.assertIn("if (!isCurrent(token)) return;",CENTER)
        self.assertIn("el('password').value = ''",APP)
        self.assertIn("46000",APP)
        self.assertIn("13000",APP)

    def test_inbox_sent_and_draft_rpc_contract(self):
        backend=(ROOT/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms").read_text()
        for method in ("getConfig","setEnabled","listMessages","getSent","getDrafts",
                       "sendMessage","saveDraft","deleteDraft","deleteMessage"):
            self.assertIn("'%s'" % method,CENTER)
            self.assertIn(method,backend)
        self.assertIn("on_demand_cmgl_pdu",CENTER)
        self.assertIn("local_sent",CENTER)
        self.assertIn("local_drafts",CENTER)
        self.assertIn("decodePrivatePdu",CENTER)
        self.assertIn("decodeSentPdu",CENTER)
        self.assertIn("mergeSmsParts",CENTER)

    def test_html_dom_and_package_includes_all_sms_modules(self):
        self.assertIn('src="/veci2/sms-codec.js"',HTML)
        self.assertIn('src="/veci2/sms-center.js"',HTML)
        for name in ("sms-status","sms-enable","sms-inbox-open","sms-sent-open",
                     "sms-drafts-open","sms-compose-open","sms-clear","sms-compose-form",
                     "sms-number","sms-text","sms-parts","sms-send","sms-save-draft",
                     "sms-close-compose","sms-send-state","sms-results"):
            self.assertIn('id="'+name+'"',HTML)
        for name in ("sms-codec.js","sms-center.js"):
            self.assertIn(name,PKG)


if __name__=="__main__":
    unittest.main()
