/* VeCI v2 SMS Center: private on-demand inbox, sent, drafts, explicit send.
 * Imported codec is reviewed client-side PDU logic; modem transport stays
 * inside the existing authenticated, serialized veCI.sms backend.
 * NO auto polling, no transmission retry, no local browser persistence.
 */
;(function () {
'use strict';
const c = globalThis.VeciSmsCodec;
const $ = id => document.getElementById(id);
let rpc, active = false, enabled = false, mode = 'unknown', generation = 0;
let sending = false, draftSelection = null;

function isCurrent(token) { return active && token === generation; }
function setStatus(text) { $('sms-status').textContent = text; }
function setResult(text) { $('sms-results').replaceChildren(); $('sms-results').textContent = text; }
function setSendStatus(text) { $('sms-send-state').textContent = text; }
function canWrite() { return active && enabled && mode === 'full'; }
function clearPrivateData() {
  generation++;
  draftSelection = null;
  $('sms-results').replaceChildren();
  $('sms-compose-form').hidden = true;
  $('sms-number').value = '';
  $('sms-text').value = '';
  $('sms-parts').textContent = 'Maksimal 4 bagian; biaya operator mungkin berlaku per bagian.';
  setSendStatus('Belum dikirim.');
}
function logout() {
  active = false;
  enabled = false;
  mode = 'unknown';
  clearPrivateData();
  setStatus('');
  $('sms-enable').hidden = true;
  for (const id of ['sms-inbox-open','sms-sent-open','sms-drafts-open','sms-compose-open']) {
    $(id).disabled = true;
  }
}
function showActions() {
  $('sms-inbox-open').disabled = !enabled;
  for (const id of ['sms-sent-open','sms-drafts-open','sms-compose-open']) {
    $(id).disabled = !canWrite();
  }
  $('sms-enable').hidden = false;
  $('sms-enable').textContent = enabled ? 'Nonaktifkan SMS' : 'Aktifkan SMS';
}
async function refresh() {
  if (!active) return;
  const token = ++generation;
  setStatus('Memeriksa SMS Center...');
  try {
    const readiness = await rpc('veci.v2','smsProvider');
    if (!isCurrent(token)) return;
    if (readiness.available !== true) throw Error('SMS backend tidak terdaftar.');
    const settings = await rpc('veci.sms','getConfig');
    if (!isCurrent(token)) return;
    if (settings.ok !== true || typeof settings.enabled !== 'boolean')
      throw Error('Status SMS tidak tersedia.');
    enabled = settings.enabled;
    mode = settings.mode === 'full' ? 'full' : 'receive_only';
    showActions();
    setStatus((enabled ? 'SMS aktif' : 'SMS nonaktif') +
      ' · Mode: ' + (mode === 'full' ? 'Inbox / Outbox / Draft' : 'Inbox saja'));
  } catch (error) {
    if (!isCurrent(token)) return;
    enabled = false;
    mode = 'unknown';
    $('sms-enable').hidden = true;
    for (const id of ['sms-inbox-open','sms-sent-open','sms-drafts-open','sms-compose-open'])
      $(id).disabled = true;
    setStatus('SMS belum siap: ' + error.message);
  }
}
async function toggleEnabled() {
  if (!active || mode === 'unknown') return;
  const target = !enabled;
  if (!window.confirm((target ? 'Aktifkan' : 'Nonaktifkan') + ' SMS Center pada router ini?'))
    return;
  const button = $('sms-enable');
  button.disabled = true;
  try {
    const result = await rpc('veci.sms','setEnabled',{state:target ? 'on' : 'off'});
    if (!active || result.ok !== true || result.enabled !== target)
      throw Error('Perubahan SMS tidak terkonfirmasi.');
    enabled = target;
    clearPrivateData();
    showActions();
    setStatus(enabled ? 'SMS aktif' : 'SMS nonaktif');
  } catch (error) { if (active) setStatus(error.message); }
  finally { button.disabled = false; }
}
function makeCard(title, meta, body) {
  const node = document.createElement('article');
  node.className = 'sms-card';
  const bold = document.createElement('strong');
  bold.textContent = title;
  const small = document.createElement('small');
  small.textContent = meta;
  const paragraph = document.createElement('p');
  paragraph.textContent = body;
  node.append(bold,small,paragraph);
  return node;
}
function action(node, label, callback) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'quiet';
  button.textContent = label;
  button.addEventListener('click', callback);
  node.append(button);
  return button;
}
async function openInbox() {
  if (!active || !enabled) return;
  const token = ++generation;
  setResult('Memuat Inbox dari modem. SMS belum dibaca mungkin ditandai dibaca...');
  try {
    const result = await rpc('veci.sms','listMessages');
    if (!isCurrent(token)) return;
    const rows = result.messages;
    if (result.ok !== true || result.source !== 'on_demand_cmgl_pdu' ||
      !Number.isSafeInteger(result.count) || result.count < 0 || result.count > 16 ||
      !Array.isArray(rows) || rows.length !== result.count)
      throw Error('Respons Inbox tidak valid.');
    const storage = ['SM','ME','MT'].includes(result.storage) ? result.storage : 'unknown';
    const seen = new Set();
    const decoded = rows.map(item => {
      if (!Number.isSafeInteger(item.index) || item.index < 0 ||
          item.index > 65535 || seen.has(item.index) ||
          typeof item.pdu !== 'string' || !/^(?:[0-9A-Fa-f]{2}){4,256}$/.test(item.pdu))
        throw Error('Record SMS tidak valid.');
      seen.add(item.index);
      let parsed = null;
      try { parsed = c.decodePrivatePdu(item.pdu); }
      catch { /* undecodable messages are listed without exposing raw PDU */ }
      return { index:item.index, status:item.status, pdu:item.pdu, decoded:parsed };
    });
    const merged = c.mergeSmsParts(decoded);
    merged.sort((a,b) =>
      (b.decoded && b.decoded.received ? b.decoded.received.unixMs : 0) -
      (a.decoded && a.decoded.received ? a.decoded.received.unixMs : 0));
    const container = document.createDocumentFragment();
    if (!merged.length) {
      const empty = document.createElement('p');
      empty.textContent = 'Inbox kosong.';
      container.append(empty);
    }
    for (const message of merged) {
      const x = message.decoded;
      const content = x ? x.text : 'Isi pesan belum dapat didekode.';
      const title = x ? 'Dari: ' + x.sender : 'SMS tersimpan';
      const time = x ? c.formatSmsDate(x.received) : 'Waktu tidak tersedia';
      const node = makeCard(title, time + ' · Slot ' +
        (message.indices || [message.index]).join(', '), content);
      if ((storage === 'SM' || storage === 'ME') && x) {
        action(node,'Hapus SMS',async () => {
          if (!isCurrent(token) || !enabled) return;
          if (!window.confirm('Hapus SMS permanen dari ' + storage +
            '? Ini tidak dapat dibatalkan.')) return;
          const segments = (message.segments || [{index:message.index,pdu:message.pdu}])
            .slice().sort((a,b) => b.index-a.index);
          try {
            for (const part of segments) {
              if (!isCurrent(token) || !enabled) return;
              const result = await rpc('veci.sms','deleteMessage',
                {index:part.index,storage,expectedPdu:part.pdu.toUpperCase()});
              if (result.ok !== true || result.deleted !== part.index ||
                  result.storage !== storage)
                throw Error('Penghapusan SMS tidak terkonfirmasi.');
            }
            if (isCurrent(token)) node.remove();
          } catch (error) { if (isCurrent(token)) setStatus(error.message); }
        });
      }
      if (x && /^\+?[0-9]{3,15}$/.test(x.sender) && canWrite()) {
        action(node,'Balas',() => {
          if (!isCurrent(token) || !canWrite()) return;
          openCompose(x.sender);
        });
      }
      container.append(node);
    }
    $('sms-results').replaceChildren(container);
    setStatus('Inbox dimuat saat diminta · ' + result.count + ' record tersimpan.');
  } catch (error) { if (isCurrent(token)) setResult('Inbox gagal dimuat: ' + error.message); }
}
async function openSent() {
  if (!canWrite()) return;
  const token = ++generation;
  setResult('Memuat Sent History...');
  try {
    const result = await rpc('veci.sms','getSent');
    if (!isCurrent(token)) return;
    if (result.ok !== true || result.source !== 'local_sent' ||
        !Number.isSafeInteger(result.count) || result.count > 30 ||
        result.count < 0 || !Array.isArray(result.messages) ||
        result.count !== result.messages.length)
      throw Error('Respons Sent tidak valid.');
    const frag = document.createDocumentFragment();
    for (const item of result.messages) {
      if (item.status !== 'accepted_by_modem' ||
          !Number.isSafeInteger(item.at) || item.at < 1000000000)
        throw Error('Record Sent tidak valid.');
      const decoded = c.decodeSentPdu(item.pdu);
      const note = new Date(item.at*1000).toLocaleString('id-ID') +
        ' · Diterima modem; penerimaan tujuan belum terverifikasi' +
        (decoded.concat ? ' · bagian '+decoded.concat.part+'/'+decoded.concat.total : '');
      frag.append(makeCard('Ke: '+decoded.to,note,decoded.text));
    }
    if (!result.count) setResult('Belum ada SMS terkirim yang tersimpan.');
    else $('sms-results').replaceChildren(frag);
  } catch (error) { if (isCurrent(token)) setResult('Sent tidak tersedia: '+error.message); }
}
function openCompose(to = '') {
  if (!canWrite()) return;
  draftSelection = null;
  $('sms-number').value = to;
  $('sms-text').value = '';
  $('sms-compose-form').hidden = false;
  setSendStatus('Belum dikirim.');
  $('sms-number').focus();
}
function updateLength() {
  if (!$('sms-text').value) return;
  try {
    const plan = c.buildSmsSubmitSegments($('sms-number').value || '+628123456789',
      $('sms-text').value,1);
    $('sms-parts').textContent = $('sms-text').value.length + ' karakter · ' +
      plan.length + ' bagian SMS. Biaya operator dapat berlaku per bagian.';
  } catch (error) { $('sms-parts').textContent = error.message; }
}
const pause = milliseconds => new Promise(resolve => setTimeout(resolve,milliseconds));
async function send(event) {
  event.preventDefault();
  if (!canWrite() || sending) return;
  const to = $('sms-number').value.trim();
  const message = $('sms-text').value;
  let plan;
  try { plan = c.buildSmsSubmitSegments(to,message,1); }
  catch (error) { setSendStatus(error.message); return; }
  if (!window.confirm('Kirim ' + plan.length + ' bagian SMS ke ' + to +
    '? Biaya SMS dapat berlaku. Jika hasil modem tidak pasti, TIDAK akan dikirim ulang otomatis.'))
    return;
  if (!canWrite()) return;
  const random = new Uint8Array(1);
  if (!globalThis.crypto || !globalThis.crypto.getRandomValues) {
    setSendStatus('Sumber acak aman tidak tersedia.');
    return;
  }
  globalThis.crypto.getRandomValues(random);
  try { plan = c.buildSmsSubmitSegments(to,message,random[0] || 1); }
  catch (error) { setSendStatus(error.message); return; }
  const token = generation;
  sending = true;
  $('sms-send').disabled = true;
  $('sms-save-draft').disabled = true;
  $('sms-number').disabled = true;
  $('sms-text').disabled = true;
  let accepted = 0;
  let failed = '';
  let historyMissing = false;
  try {
    for (let i=0;i<plan.length;i++) {
      if (!isCurrent(token) || !canWrite()) {
        failed = 'Sesi atau layanan SMS berubah; sisa pesan tidak dikirim.';
        break;
      }
      if (i) {
        setSendStatus(accepted+'/'+plan.length+' diterima modem; menunggu bagian selanjutnya...');
        await pause(5300); // 5 second modem rate limiter; never a retry
      }
      if (!isCurrent(token) || !canWrite()) {
        failed = 'Sesi berubah sebelum bagian selanjutnya.';
        break;
      }
      setSendStatus('Mengirim bagian '+(i+1)+'/'+plan.length+'...');
      let r;
      try { r = await rpc('veci.sms','sendMessage',{pdu:plan[i]}); }
      catch {
        failed = 'Hasil modem tidak pasti pada bagian '+(i+1)+'. Jangan kirim ulang otomatis.';
        break;
      }
      if (!isCurrent(token)) return;
      if (r.ok === true && r.status === 'accepted_by_modem') {
        accepted++;
        if (r.history_saved === false) historyMissing = true;
      } else {
        failed = 'Bagian '+(i+1)+' tidak dikonfirmasi diterima modem. Jangan kirim ulang otomatis.';
        break;
      }
    }
    if (isCurrent(token)) {
      if (accepted === plan.length) {
        $('sms-text').value = '';
        draftSelection = null;
        setSendStatus('Semua '+accepted+' bagian diterima modem. Pengiriman ke penerima belum dikonfirmasi.'+
          (historyMissing ? ' Sebagian riwayat tidak tersimpan.' : ''));
      } else setSendStatus(accepted+'/'+plan.length+' bagian diterima modem. '+failed);
    }
  } finally {
    sending = false;
    $('sms-send').disabled = false;
    $('sms-save-draft').disabled = false;
    $('sms-number').disabled = false;
    $('sms-text').disabled = false;
  }
}
async function openDrafts() {
  if (!canWrite()) return;
  const token=++generation;
  setResult('Memuat Drafts...');
  try {
    const data=await rpc('veci.sms','getDrafts');
    if (!isCurrent(token)) return;
    if (data.ok!==true || data.source!=='local_drafts' ||
        !Number.isSafeInteger(data.count) || data.count<0 || data.count>10 ||
        !Array.isArray(data.drafts) || data.drafts.length!==data.count)
      throw Error('Respons Draft tidak valid.');
    const frag=document.createDocumentFragment();
    const seen=new Set();
    for (const item of data.drafts) {
      if (!Number.isSafeInteger(item.id) || item.id<1 || item.id>10 ||
          seen.has(item.id) || !Number.isSafeInteger(item.at)) throw Error('Draft invalid');
      seen.add(item.id);
      const decoded=c.decodeSentPdu(item.pdu);
      const card=makeCard('Ke: '+decoded.to,'Draft tidak terkirim',decoded.text);
      action(card,'Edit draft',() => {
        if (!isCurrent(token) || !canWrite()) return;
        openCompose(decoded.to);
        $('sms-text').value=decoded.text;
        draftSelection={id:item.id,expectedPdu:item.pdu};
        setSendStatus('Mengedit draft lama, belum dikirim.');
      });
      action(card,'Hapus draft',async () => {
        if (!isCurrent(token) || !canWrite()) return;
        if (!window.confirm('Hapus draft ini permanen?')) return;
        try {
          const deleted=await rpc('veci.sms','deleteDraft',
            {id:item.id,expectedPdu:item.pdu});
          if (deleted.ok!==true || deleted.deleted!==item.id)
            throw Error('Hapus draft tidak terkonfirmasi.');
          if (isCurrent(token)) card.remove();
        } catch (error) { if (isCurrent(token)) setStatus(error.message); }
      });
      frag.append(card);
    }
    if (!data.count) setResult('Belum ada draft.');
    else $('sms-results').replaceChildren(frag);
  } catch (error) { if (isCurrent(token)) setResult('Draft gagal dimuat: '+error.message); }
}
async function saveDraft() {
  if (!canWrite() || sending) return;
  let pdu;
  try { pdu=c.buildSmsSubmit($('sms-number').value.trim(),$('sms-text').value); }
  catch (error) { setSendStatus('Draft harus satu SMS: '+error.message); return; }
  const selected=draftSelection;
  $('sms-save-draft').disabled=true;
  try {
    const result=await rpc('veci.sms','saveDraft',{
      id:selected ? selected.id : 0,
      expectedPdu:selected ? selected.expectedPdu : '-',
      pdu
    });
    if (!active) return;
    if (result.ok!==true || result.saved!==true ||
        !Number.isSafeInteger(result.id) || result.id<1 || result.id>10)
      throw Error('Penyimpanan draft tidak dikonfirmasi.');
    draftSelection={id:result.id,expectedPdu:pdu};
    setSendStatus('Draft '+result.id+' tersimpan. SMS belum dikirim.');
  } catch (error) { if (active) setSendStatus('Draft gagal: '+error.message); }
  finally { $('sms-save-draft').disabled=false; }
}
function init(remote) {
  rpc=remote;
  $('sms-enable').addEventListener('click',toggleEnabled);
  $('sms-inbox-open').addEventListener('click',openInbox);
  $('sms-sent-open').addEventListener('click',openSent);
  $('sms-drafts-open').addEventListener('click',openDrafts);
  $('sms-compose-open').addEventListener('click',() => openCompose());
  $('sms-clear').addEventListener('click',() => { clearPrivateData(); setResult(''); });
  $('sms-compose-form').addEventListener('submit',send);
  $('sms-close-compose').addEventListener('click',() => {
    if (!sending) { $('sms-compose-form').hidden=true; $('sms-text').value=''; }
  });
  $('sms-number').addEventListener('input',updateLength);
  $('sms-text').addEventListener('input',updateLength);
  $('sms-save-draft').addEventListener('click',saveDraft);
}
function activate() { active=true; }
globalThis.VeciSmsCenter=Object.freeze({init,activate,refresh,logout});
})();
