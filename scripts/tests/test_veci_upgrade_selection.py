"""Use the actual UI handlers and deliver manual/OTA verification replies out of order."""
from pathlib import Path
import subprocess
import unittest

APP = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/app.js"


class UpgradeSelectionTests(unittest.TestCase):
    def test_latest_operator_selection_owns_install_button(self):
        js = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm'), fs = require('node:fs'), crypto = require('node:crypto');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    addEventListener(event, fn) { this[event] = fn; },
    querySelector() { return node(id + '-output'); }
  });
  return nodes.get(id);
}
const manual = new Blob(['manual']);
const digest = crypto.createHash('sha256').update('manual').digest('hex');
const manifest = {schema:1,channel:'stable',available:true,target:'ramips/mt76x8',
  board:'zbtlink,zbt-we5927',supported_devices:['zbtlink,zbt-we5927'],size:3, sha256:'a'.repeat(64),
  firmware_url:'https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/v2/ota.bin'};
const form = node('firmware-check'), ota = node('firmware-channel-verify');
form.elements = {image:{files:[manual]}, digest:{value:digest}};
const pending = new Map();
const ctx = vm.createContext({document:{getElementById:node, addEventListener(){}}, Blob,
  crypto:crypto.webcrypto, manifest, fetch:url => new Promise(resolve => pending.set(url,resolve))});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8') + ";sid='1'.repeat(32);stableRelease=manifest;",ctx);
const manualUrl='/cgi-bin/veci2-verify', otaUrl=manualUrl+'?stable';
const startManual = () => form.submit({preventDefault(){}});
async function respond(url, sha) {
  for(let i=0; !pending.has(url) && i<100; i++) await new Promise(r=>setTimeout(r,1));
  assert.ok(pending.has(url));
  pending.get(url)({ok:true,json:async()=>({verified:true,install_allowed:true,sha256:sha,ticket:'b'.repeat(64)})});
  pending.delete(url);
}
const candidate = () => vm.runInContext('installCandidate?.digest',ctx);
(async()=>{
  let first = ota.click();
  let latest = startManual();
  await respond(manualUrl,digest); await latest;
  await respond(otaUrl,manifest.sha256); await first;
  assert.equal(candidate(),digest,'late OTA replaced manual choice');
  first=startManual();
  while(!pending.has(manualUrl)) await new Promise(r=>setTimeout(r,1));
  latest=ota.click();
  assert.equal(candidate(),undefined,'previous install still offered during OTA verification');
  await respond(otaUrl,manifest.sha256); await latest;
  await respond(manualUrl,digest); await first;
  assert.equal(candidate(),manifest.sha256,'late upload replaced OTA choice');
  const stale=ota.click();
  form.input();
  await respond(otaUrl,manifest.sha256); await stale;
  assert.equal(candidate(),undefined,'old ticket reappeared after file edit');
  assert.equal(node('firmware-install').hidden,true);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        subprocess.run(["node", "-e", js, str(APP)], check=True, timeout=6)
