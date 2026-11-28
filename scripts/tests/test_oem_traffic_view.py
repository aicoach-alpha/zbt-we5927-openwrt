import subprocess,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/frontend/traffic-view.js"
class TrafficView(unittest.TestCase):
 def test_unknown_and_observed_values(self):
  script="""
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const component=vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'));
const amount=component.methods.amount;
assert.equal(amount.call({sample:null},'lte_rx_bytes'),'—');
assert.equal(amount.call({sample:{history_state:'observed_partial',lte_rx_bytes:'0'}},'lte_rx_bytes'),'0 byte');
assert.equal(amount.call({sample:{history_state:'observed_partial',lte_rx_bytes:''}},'lte_rx_bytes'),'—');
assert.equal(amount.call({sample:{history_state:'unavailable',lte_rx_bytes:'123'}},'lte_rx_bytes'),'—');
assert.equal(amount.call({sample:{history_state:'observed_partial',lte_rx_bytes:'abc'}},'lte_rx_bytes'),'—');
"""
  subprocess.run(["node","-e",script,str(P)],check=True,timeout=5)
