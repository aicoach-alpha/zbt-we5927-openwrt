"""Run the shipped cron UI and BusyBox record parser on deterministic inputs."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "rebuild/veci-v2/packages"
RUNTIME = PACKAGE / "veci-v2-runtime"
UI = PACKAGE / "veci-v2-ui/files/www/veci2"


class CronAcceptance(unittest.TestCase):
    def test_parser_add_remove_preserves_oem_and_rejects_invalid_ranges(self):
        def parse(mode, rows, **values):
            args = ["busybox", "awk", "-v", f"mode={mode}"]
            for key, value in values.items():
                args.extend(["-v", f"{key}={value}"])
            return subprocess.run(args + ["-f", str(RUNTIME / "veci2-cron.awk")],
                                  text=True, input=rows, capture_output=True, timeout=3)

        original = "# oem\nHOME=/root\n@reboot /vendor/init\n0 1 * * * /vendor/weekly --secret=test\n"
        values = dict(schedule="*/15 2 * * 1-6", active="0", cmd="/bin/busybox free")
        added = parse("add", original, **values)
        self.assertEqual(added.returncode, 0)
        self.assertEqual(added.stdout, original + "# VeCI paused: */15 2 * * 1-6 /bin/busybox free\n")
        removed = parse("remove", added.stdout, row="5")
        self.assertEqual((removed.returncode, removed.stdout), (0, original))
        for invalid in ["*/0 * * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 7"]:
            self.assertNotEqual(parse("add", original, **(values | dict(schedule=invalid))).returncode, 0)
        for row in ["1", "2", "3", "6"]:
            self.assertNotEqual(parse("remove", original, row=row).returncode, 0)
        public = parse("list", original)
        self.assertEqual(public.stdout, "4\t1\t0 1 * * *\tweekly\n")

    def test_native_ui_add_edit_remove_confirmation_and_acl(self):
        acl = json.loads((RUNTIME / "veci2-cron-acl.json").read_text())["veci-v2-cron"]
        self.assertEqual(acl["read"]["ubus"]["veci.v2.cron"], ["status"])
        self.assertEqual(set(acl["write"]["ubus"]["veci.v2.cron"]), {"add", "save", "remove"})
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const controls = new Map();
global.el = (id) => {
  if (!controls.has(id)) controls.set(id, {
    value:'', replaceChildren(...items){this.value=items[0]?.value || '';}, reportValidity(){return true;}
  });
  return controls.get(id);
};
global.Option = function(name, value){this.value=value;};
global.sid = 'session';
let confirm=true;
global.window = {confirm:()=>confirm};
const calls=[];
let jobs=[];
global.rpc = async (obj, method, args, session) => {
  assert.equal(obj,'veci.v2.cron'); assert.equal(session,sid);
  calls.push([method,args]);
  if (method==='add' || method==='save') jobs=[{row:'1',label:'memory',schedule:args.schedule,enabled:args.enabled==='1'}];
  if (method==='remove') jobs=[];
  return {ok:true, jobs, revision:String(calls.length)};
};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const tick = () => new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await el('cron-read').onclick(); assert.equal(el('cron-fields').disabled,false);
  el('cron-task').value='memory'; el('cron-schedule').value='0 12 * * *';
  confirm=false; el('cron-add').onclick(); await tick(); assert.equal(calls.length,1);
  confirm=true; el('cron-add').onclick(); await tick();
  assert.deepEqual(calls[1],['add',{revision:'1',schedule:'0 12 * * *',enabled:'1',task:'memory'}]);
  el('cron-schedule').value='1 12 * * *'; el('cron-enabled').checked=false;
  el('cron-form').onsubmit({preventDefault(){}}); await tick();
  assert.deepEqual(calls[2],['save',{revision:'2',row:'1',schedule:'1 12 * * *',enabled:'0'}]);
  confirm=false; el('cron-remove').onclick(); await tick(); assert.equal(calls.length,3);
  confirm=true; el('cron-remove').onclick(); await tick();
  assert.deepEqual(calls[3],['remove',{revision:'3',row:'1'}]);
  assert.equal(el('cron-remove').disabled,true);
  VeciCron.reset(); assert.equal(el('cron-fields').disabled,true);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        subprocess.run(["node", "-e", script, str(UI / "cron.js")], check=True, timeout=5)
        html = (UI / "index.html").read_text()
        for suffix in ["read", "fields", "save", "remove", "add", "task", "form"]:
            self.assertEqual(html.count(f'id="cron-{suffix}"'), 1)

