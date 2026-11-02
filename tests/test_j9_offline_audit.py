"""Non-live J9 gate regression tests: uses only synthetic temporary files."""
import hashlib
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
m=Path(__file__).resolve().parents[1]/'scripts/j9_offline_audit.py'
spec=importlib.util.spec_from_file_location('j9',m)
j9=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=j9
spec.loader.exec_module(j9)

def fixture(root):
    fw=root/'fw'; feed=root/'feed';fw.mkdir();feed.mkdir()
    def put(p,value):
        q=feed/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(value)
    for x in j9.INDEXES: put(x,b'INDEX'*100)
    for a in j9.APPS: put('packages/mipsel_24kc/base/veci-app-'+a+'-1-r1.apk',b'A'*200)
    for name in j9.DEPENDENCIES:
        folder='targets/ramips/mt76x8/packages' if name.startswith('kmod-') else 'packages/mipsel_24kc/packages'
        put(folder+'/'+name+'-6.12.112-r1.apk',b'X'*200)
    for x in range(15): put('packages/mipsel_24kc/base/extra%d-1-r1.apk'%x,b'X'*200)
    manifest='\n'.join(x+' - 1-r1' for x in sorted(j9.CORE))+'\nkernel - 6.12.112~abc-r1\n'
    (fw/j9.MANIFEST).write_text(manifest)
    (fw/j9.IMAGE).write_bytes(b'firmware'*100)
    pins='\n'.join('%s: %040x'%(n,i) for i,n in enumerate(('OpenWrt','packages','luci','routing','telephony','video'),1))
    rows=['%s bin/packages/mipsel_24kc/base/veci-app-%s-1-r1.apk'%(200,a) for a in j9.APPS]
    (fw/'J8C-INVENTORY.txt').write_text(pins+'\nSelected app APKs:\n'+'\n'.join(rows)+'\nMatched kernel packages:\n')
    h=lambda p:hashlib.sha256((fw/p).read_bytes()).hexdigest()
    (fw/'target-sha256sums').write_text(h(j9.IMAGE)+' *'+j9.IMAGE+'\n'+h(j9.MANIFEST)+' *'+j9.MANIFEST+'\n')
    names=['J8C-INVENTORY.txt','target-sha256sums',j9.IMAGE,j9.MANIFEST]
    (fw/'J8C-SHA256SUMS.txt').write_text(''.join(h(p)+'  '+p+'\n' for p in names))
    return fw,feed

class TestGate(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.fw,self.feed=fixture(self.root)
    def run_gate(self):
        return j9.audit(j9.Artifact(self.fw),j9.Artifact(self.feed),'37913407078')
    def test_pass_is_still_no_go(self):
        a=self.run_gate()
        self.assertEqual(a['j9'],'OFFLINE_PASS')
        self.assertEqual(a['release_decision'],'NO_GO')
        self.assertEqual(a['gates']['live_router_uat'],'NOT_TESTED')
    def test_hash_mutation(self):
        with (self.fw/j9.IMAGE).open('ab') as f:f.write(b'bad')
        with self.assertRaisesRegex(j9.GateError,'SHA256'):self.run_gate()
    def test_missing_app(self):
        (self.feed/'packages/mipsel_24kc/base/veci-app-guest-1-r1.apk').unlink()
        with self.assertRaises(j9.GateError):self.run_gate()
    def test_missing_uspot_not_masked_by_uspot_www(self):
        (self.feed/'packages/mipsel_24kc/packages/uspot-6.12.112-r1.apk').unlink()
        with self.assertRaisesRegex(j9.GateError,'App/dependency'):self.run_gate()
    def test_wrong_kernel(self):
        p=self.feed/'targets/ramips/mt76x8/packages/kmod-wireguard-6.12.112-r1.apk'
        p.rename(p.with_name('kmod-wireguard-6.12.94-r1.apk'))
        with self.assertRaises(j9.GateError):self.run_gate()
    def test_index_missing(self):
        (self.feed/j9.INDEXES[0]).unlink()
        with self.assertRaises(j9.GateError):self.run_gate()
    def test_bad_run_id(self):
        with self.assertRaises(j9.GateError):j9.audit(j9.Artifact(self.fw),j9.Artifact(self.feed),'invalid')
    def test_zips(self):
        def archive(path,name):
            dst=self.root/name
            with zipfile.ZipFile(dst,'w') as z:
                for f in path.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(path))
            return dst
        a=j9.audit(j9.Artifact(archive(self.fw,'fw.zip')),j9.Artifact(archive(self.feed,'feed.zip')),'37913407078')
        self.assertEqual(a['j9'],'OFFLINE_PASS')
    def test_zip_traversal(self):
        z=self.root/'bad.zip'
        with zipfile.ZipFile(z,'w') as f:f.writestr('../bad','bad')
        with self.assertRaisesRegex(j9.GateError,'Unsafe ZIP'):j9.Artifact(z)
    def test_duplicate_zip(self):
        import warnings
        z=self.root/'duplicate.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(z,'w') as f:f.writestr('a','1');f.writestr('a','2')
        with self.assertRaisesRegex(j9.GateError,'Duplicate ZIP'):j9.Artifact(z)
