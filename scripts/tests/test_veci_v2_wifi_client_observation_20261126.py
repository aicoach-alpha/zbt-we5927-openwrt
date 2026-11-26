"""Read-only source/UI contract for truthful MT76 association status."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/'rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/wifi-controls.js'
BACK=ROOT/'rebuild/veci-v2/packages/veci-v2-runtime/veci2-wifi-controls'

class ClientObservationContract(unittest.TestCase):
    def test_real_ui_render_handles_five_distinct_cases(self):
        js=r"""
const assert=require('assert');
const fs=require('fs'),vm=require('vm');
const text=fs.readFileSync(process.argv[1],'utf8');
const first=text.indexOf('  function render(data) {');
const last=text.indexOf('\n  async function run(',first);
assert(first>=0 && last>first);
const station={textContent:''};
const channel={replaceChildren(){},add(){},selectedIndex:0};
const access={mode:{value:''},addresses:{value:''}}, security={mode:{value:''}};
const fixed={channel};
const env={access,security,fixed,
  el(id){assert.equal(id,'station-list');return station;},
  Option:function(t,v){this.text=t;this.value=v;}
};
const render=vm.runInNewContext(text.slice(first,last)+'\nrender;',env);
function check(state,clients,expected){
  render({access:'disable',encryption:'psk2',channels:[],addresses:[],clients,
    client_observation:{state}});
  assert(station.textContent.includes(expected),state+' -> '+station.textContent);
}
check('zero_observed',[],'0 klien terdeteksi saat pemeriksaan');
check('observed',['02:aa:bb:cc:dd:ee'],'02:aa:bb:cc:dd:ee');
check('mismatch',[],'jumlah klien berbeda');
check('unavailable',undefined,'belum dapat diverifikasi');
check(undefined,undefined,'belum dapat diverifikasi');
render({access:'disable',encryption:'psk2',channels:[],addresses:[],clients:[],
  client_observation:{state:'zero_observed'},
  ap_snapshot:{interface:'phy0-ap0',bssid:'02:fe:dc:ba:98:76',
    rx_bytes:'123456789',tx_bytes:'987654321'}});
assert(station.textContent.includes('BSSID: 02:fe:dc:ba:98:76'));
assert(station.textContent.includes('123456789 / 987654321 byte'));
assert(station.textContent.includes('bukan bukti klien aktif'));
assert(station.textContent.includes('\\nBSSID:')===false);

console.log('UI_CLIENT_OBSERVATION_FIVE_CASES_PASS');
"""
        result=subprocess.run(['node','-e',js,str(UI)],capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('FIVE_CASES_PASS',result.stdout)
    def test_dual_source_is_read_only_and_never_equates_zero_to_disconnected(self):
        s=BACK.read_text()
        self.assertIn('hostapd_station_count() (',s)
        self.assertIn('json_select clients',s)
        self.assertIn('get_clients',s)
        self.assertIn('client_state=zero_observed',s)
        self.assertIn('client_state=mismatch',s)
        self.assertIn('client_state=unavailable',s)
        self.assertIn('json_add_object client_observation',s)
        self.assertNotIn('json_add_boolean root_cause_fixed 1',s)
        subprocess.run(['busybox','ash','-n',str(BACK)],check=True,timeout=5)

if __name__=='__main__':unittest.main()
