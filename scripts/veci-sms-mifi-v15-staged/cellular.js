import { badge, escapeHtml, setBusy } from '../lib/dom.js';

function metric(label, value, suffix = '') {
	const display = value === undefined || value === null || value === '' ? '—' : `${value}${suffix}`;
	return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(display)}</strong></div>`;
}

function normalizeOperator(value) {
	const text = String(value || '').trim();
	if (!text) return 'No operator';

	const parts = text.split(/\s+/);
	if (parts.length % 2 === 0) {
		const half = parts.length / 2;
		const first = parts.slice(0, half).join(' ');
		const second = parts.slice(half).join(' ');
		if (first.toLowerCase() === second.toLowerCase()) return first;
	}

	return text;
}


/* Decode only after explicitly authenticated, single-use private readSlot.
 * No persistence, no logging. Supports GSM7 & UCS2 SMS-DELIVER.
 */

function formatSmsDate(received) {
  if (!received || !Number.isFinite(received.unixMs))return 'Time unavailable';
  const d=new Date(received.unixMs);
  if (!Number.isFinite(d.getTime()))return 'Time unavailable';
  return d.toLocaleString('id-ID', {day:'2-digit',month:'short',year:'numeric',
    hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function mergeSmsParts(rows) {
  const groups=new Map(),display=[];
  for (const row of rows) {
    const m=row.decoded, c=m?.concat;
    // Do not merge unrelated messages with same reused reference: bind
    // alphanumeric sender, total count and a 48h window of SCTS.
    if(!c || !m.received || c.total<=1){display.push(row);continue;}
    const key=[m.sender,c.ref,c.total].join('|');
    const candidates=groups.get(key)||[];
    let group=candidates.find(g=>Math.abs(g.epoch-m.received.unixMs)<=48*3600000 &&
      !g.parts.has(c.part));
    if(!group){group={epoch:m.received.unixMs,parts:new Map(),total:c.total};candidates.push(group);groups.set(key,candidates);display.push({group,decoded:m});}
    group.parts.set(c.part,row);
  }
  return display.flatMap(item=>{
    if(!item.group)return [item];
    const group=item.group;
    if(group.parts.size!==group.total){
      // Display every available segment individually, never silently
      // hide the other parts when a multipart SMS is incomplete.
      return [...group.parts].sort((a,b)=>a[0]-b[0]).map(v=>({
        ...v[1],decoded:{...v[1].decoded,text:v[1].decoded.text+
          ' (part '+v[0]+'/'+group.total+')'}}));
    }
    const ordered=[...group.parts].sort((a,b)=>a[0]-b[0]).map(v=>v[1]);
    return [{...ordered[0],decoded:{...ordered[0].decoded,
      text:ordered.map(r=>r.decoded.text).join(''),concat:null,
      multipartCount:ordered.length},indices:ordered.map(r=>r.index),
      segments:ordered.map(r=>({index:r.index,pdu:r.pdu}))}];
  });
}

function decodePrivatePdu(hex) {
  if(typeof hex!=="string" || !/^(?:[0-9A-Fa-f]{2}){4,256}$/.test(hex))throw Error("PDU");
  const bytes=Uint8Array.from(hex.match(/../g),b=>parseInt(b,16));
  let p=0;
  function one(){if(p>=bytes.length)throw Error("PDU truncated");return bytes[p++];}
  const gsmPoints=[64,163,36,165,232,233,249,236,242,199,10,216,248,13,197,229,916,95,934,915,923,937,928,936,931,920,926,0,198,230,223,201,32,33,34,35,164,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,161,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,196,214,209,220,167,191,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,228,246,241,252,224];
  const ext={10:12,20:94,40:123,41:125,47:92,60:91,61:126,62:93,64:124,101:8364};
  function unpack7(arr,count,offset=0){
    let s="",esc=false;
    for(let i=0;i<count;i++){
      let bit=offset+i*7, k=bit>>3,shift=bit&7;
      if(k>=arr.length || (shift>1 && k+1>=arr.length))throw Error("GSM7 truncated");
      let v=((arr[k]>>shift)|((arr[k+1]||0)<<(8-shift)))&127;
      if(esc){if(ext[v]===undefined)throw Error("GSM7 extension");s+=String.fromCodePoint(ext[v]);esc=false;}
      else if(v===27){esc=true;}
      else {const cp=gsmPoints[v];if(!cp)throw Error("GSM7 invalid");s+=String.fromCodePoint(cp);}
    }
    if(esc)throw Error("GSM7 dangling escape");
    return s;
  }
  const sca=one();if(sca>12 || p+sca>=bytes.length)throw Error("SMSC");p+=sca;
  const fo=one();if((fo&3)!==0 || (fo&128))throw Error("Not SMS-DELIVER");
  const udhi=!!(fo&64), digits=one(),toa=one();
  if(!(toa&128) || digits<1 || digits>20)throw Error("Sender");
  const alpha=(toa&112)===80;
  // TS 23.040 alphanumeric OA length counts USEFUL SEMI-OCTETS,
  // not characters or septets. A 10-character sender uses 18 nibbles.
  const addrBytes=Math.ceil(digits/2);
  if(p+addrBytes>bytes.length)throw Error("Sender truncated");
  let sender="";
  if(alpha){
    const septetCount=Math.floor(digits*4/7);
    if(!septetCount || septetCount>11)throw Error("Alpha sender length");
    sender=unpack7(bytes.slice(p,p+addrBytes),septetCount);
  }
  else {
    if((toa&112)===16)sender="+";
    for(let i=0;i<digits;i++){let v=(i&1)?bytes[p+(i>>1)]>>4:bytes[p+(i>>1)]&15;if(v>9)throw Error("Sender digit");sender+=String(v);}
    if((digits&1) && ((bytes[p+addrBytes-1]>>4)!==15))throw Error("Sender filler");
  }
  p+=addrBytes;
  if(p+10>bytes.length)throw Error("Header truncated");
  one();const dcs=one();
  // 23.038 DCS: general coding, message-waiting indication and
  // 1111xxxx message classes (commonly used for operator SMS).
  let alphabet;
  if((dcs&192)===0){
    if(dcs&32)throw Error("Compressed SMS");
    alphabet=(dcs>>2)&3;
  }else if((dcs&240)===240){
    alphabet=(dcs&4)?1:0;
  }else if((dcs&240)===224){
    alphabet=2;
  }else if((dcs&240)===192 || (dcs&240)===208){
    alphabet=0;
  }else{
    throw Error("Unsupported DCS");
  }
  if(alphabet===1)throw Error("Binary SMS");
  if(alphabet!==0 && alphabet!==2)throw Error("Unsupported alphabet");
  // TP-Service-Centre-Time-Stamp: 7 swapped semi-octets; last holds
  // signed UTC offset in quarter-hours. Keep original network time zone.
  const scts=bytes.slice(p,p+7);
  p+=7;
  const decodeBcd=(v)=>{const lo=v&15,hi=(v>>4)&15;if(lo>9||hi>9)throw Error("SCTS BCD");return lo*10+hi;};
  let received=null;
  try {
    const yy=decodeBcd(scts[0]);
    const year=yy<90?2000+yy:1900+yy;
    const month=decodeBcd(scts[1]),day=decodeBcd(scts[2]);
    const hour=decodeBcd(scts[3]),minute=decodeBcd(scts[4]),second=decodeBcd(scts[5]);
    const sign=(scts[6]&8)?-1:1;
    const quarters=(scts[6]&7)*10+(scts[6]>>4);
    if(month<1||month>12||day<1||day>31||hour>23||minute>59||second>59||quarters>79)
      throw Error("SCTS range");
    const local=Date.UTC(year,month-1,day,hour,minute,second);
    const candidate=new Date(local);
    if(candidate.getUTCFullYear()!==year||candidate.getUTCMonth()+1!==month||
       candidate.getUTCDate()!==day)throw Error("SCTS date");
    const timezoneMinutes=sign*quarters*15;
    received={unixMs:local-timezoneMinutes*60000,timezoneMinutes,
      networkTime:`${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')} ${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}:${String(second).padStart(2,'0')}`};
  } catch { /* Broken SCTS never hides otherwise valid message text. */ }
  const udl=one(),data=bytes.slice(p);
  let header=0,concat=null;
  if(udhi){
    if(!data.length)throw Error("UDH");
    header=data[0]+1;
    if(header<3||header>data.length)throw Error("UDH invalid");
    // Concatenation IE: 8-bit 00/03 and 16-bit 08/04.
    for(let i=1;i<header;){
      if(i+2>header)throw Error("UDH IE");
      const ie=data[i++],size=data[i++];
      if(i+size>header)throw Error("UDH IE length");
      if((ie===0&&size===3)||(ie===8&&size===4)){
        const ref=ie===0?data[i]:(data[i]<<8)|data[i+1];
        const total=data[i+size-2],part=data[i+size-1];
        if(!total||total>32||part<1||part>total)throw Error("UDH multipart");
        concat={ref,total,part};
      }
      i+=size;
    }
  }
  let text="";
  if(alphabet===0){
    if(udl>160 || data.length!==Math.ceil(udl*7/8))throw Error("GSM7 size");
    const skip=udhi?Math.ceil(header*8/7):0;
    if(skip>udl)throw Error("UDH size");
    text=unpack7(data,udl-skip,skip*7);
  }else{
    if(udl>140 || data.length!==udl || ((udl-header)&1))throw Error("UCS2 size");
    for(let i=header;i<data.length;i+=2){
      let cp=(data[i]<<8)|data[i+1];
      if(cp>=0xD800 && cp<=0xDBFF){
        if(i+3>=data.length)throw Error("UCS2 surrogate");
        const low=(data[i+2]<<8)|data[i+3];
        if(low<0xDC00 || low>0xDFFF)throw Error("UCS2 surrogate");
        cp=0x10000+((cp-0xD800)<<10)+(low-0xDC00);i+=2;
      }else if(cp>=0xDC00 && cp<=0xDFFF)throw Error("UCS2 surrogate");
      if(!cp)throw Error("NUL");
      text+=String.fromCodePoint(cp);
    }
  }
  if(!sender || sender.length>80 || text.length>4096)throw Error("Message size");
  return {sender,text,received,concat};
}

export default {
	id: 'cellular',
	title: 'Cellular',
	navLabel: 'Cellular',
	eyebrow: 'MOBILE NETWORK',
	icon: 'signal',
	capability: 'cellular',

	async render({ api, root, toast, confirm }) {
		const status = await api.cellularStatus();

		const signalPercent = Number.isFinite(Number(status.signal_percent)) ? Number(status.signal_percent) : null;
		const signalDbm = Number.isFinite(Number(status.signal_dbm)) ? Number(status.signal_dbm) : null;
		const online = status.online === true || status.online === 1 || status.online === '1';
		const sim = status.sim || '—';
		const model = status.model || status.manufacturer || 'Cellular modem';
		const operator = normalizeOperator(status.operator);
		const technology = status.access_tech || status.registration_status || 'Unknown';

		root.innerHTML = `
			<div class="page-intro">
				<div>
					<h2>Mobile connection</h2>
					<p>Signal, SIM and modem health from the cellular integration installed on this router. Data-link state does not by itself verify Internet reachability.</p>
				</div>
				${badge(online ? 'Data link active' : 'Data link down', online ? 'success' : 'danger')}
			</div>

			<div class="cellular-hero">
				<section class="panel">
					<div class="panel-heading">
						<div>
							<p class="eyebrow">MODEM</p>
							<h3>${escapeHtml(model)}</h3>
						</div>
						<strong class="cellular-operator">${escapeHtml(operator)}</strong>
					</div>
					<div class="signal-block">
						<div>
							<span class="signal-number">${signalPercent === null ? '—' : escapeHtml(String(signalPercent))}<small>${signalPercent === null ? '' : '%'}</small></span>
							<span class="signal-label">Signal strength</span>
						</div>
						<div class="signal-bars" aria-label="Signal strength">
							${[20, 40, 60, 80, 100]
								.map(
									limit =>
										`<span class="${signalPercent !== null && signalPercent >= limit ? 'active' : ''}"></span>`
								)
								.join('')}
						</div>
					</div>
					<div class="detail-list">
						${metric('Technology', technology)}
						${metric('Signal', signalDbm, signalDbm === null ? '' : ' dBm')}
						${metric('Registration', status.registration_status || status.registration)}
						${metric('Packet service', status.packet_status || status.packet_attach)}
					</div>
				</section>

				<section class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">CONNECTION</p><h3>SIM & data</h3></div>
					</div>
					<div class="detail-list">
						${metric('Active SIM', sim)}
						${metric('SIM status', status.sim_status)}
						${metric('IPv4', status.ipv4)}
						${metric('Gateway', status.gateway)}
						${metric('Data interface', status.data_interface)}
						${metric('Mode', status.mode)}
						<div id="cellular-internet-status"><span>Internet</span><strong>${online ? 'Checking…' : 'Unavailable'}</strong></div>
					</div>
					<div class="cellular-actions">
						<button class="button button-secondary" id="cellular-reconnect" type="button">Reconnect data</button>
						${status.sim !== undefined ? '<button class="button button-secondary" id="cellular-switch-sim" type="button">Switch SIM</button>' : ''}
					</div>
				</section>
			</div>

			<section class="panel" aria-labelledby="cellular-sms-mifi-title">
				<div class="panel-heading">
					<div><p class="eyebrow">MESSAGING</p><h3 id="cellular-sms-mifi-title">SMS Inbox</h3></div>
				</div>
				<div class="cellular-actions">
					<label for="cellular-sms-enabled"><input id="cellular-sms-enabled" type="checkbox" disabled /> Enable SMS</label>
				</div>
				<p id="cellular-sms-state" role="status">Checking SMS settings…</p>
				<div id="cellular-sms-inbox-controls" hidden>
					<p>View sender and full message text like a standard MiFi. Opening the Inbox may mark unread SMS as read.</p>
					<div class="cellular-actions">
						<button class="button button-secondary" id="cellular-sms-open" type="button">Open Inbox</button>
						<button class="button button-secondary" id="cellular-sms-clear" type="button">Clear screen</button>
					</div>
					<div class="cellular-actions" style="margin:12px 0;display:flex;gap:12px;flex-wrap:wrap;align-items:center">
						<label for="cellular-sms-search" style="flex:1;min-width:180px">Search Inbox
							<input id="cellular-sms-search" type="search" placeholder="Sender or message text" autocomplete="off" disabled style="display:block;width:100%;margin-top:4px"/>
						</label>
						<label for="cellular-sms-filter">Status
							<select id="cellular-sms-filter" disabled style="display:block;margin-top:4px">
								<option value="all">All messages</option>
								<option value="unread">Unread</option>
								<option value="read">Read</option>
							</select>
						</label>
					</div>
					<div id="cellular-sms-messages" role="status" aria-live="polite">Click Open Inbox to load messages.</div>
				</div>
			</section>

			<div class="notice-card">
				<strong>Hardware-aware integration</strong>
				<p>VeCI Core does not assume a specific modem or router. This page appears only when the firmware exposes the standard <code>veci.cellular</code> provider.</p>
			</div>
		`;

		if (online) {
			api.veci('internetStatus', {}, { timeout: 3000 })
				.then(internet => {
					const value = root.querySelector('#cellular-internet-status strong');
					if (!value) return;
					if (internet.status === 'reachable' && internet.reachable === true) value.textContent = 'Reachable';
					else if (internet.status === 'unreachable' && internet.reachable === false)
						value.textContent = 'Unavailable';
					else value.textContent = 'Not verified';
				})
				.catch(() => {
					const value = root.querySelector('#cellular-internet-status strong');
					if (value) value.textContent = 'Not verified';
				});
		}

		// SMS is opt-in by persistent on/off setting. NO modem query on page load.
		// This uses the SAME authenticated write-only veci.sms ACL already used
		// by the functioning v1.3.1 metadata Inbox. No extra confirmation/token.
		const smsToggle = root.querySelector('#cellular-sms-enabled');
		const smsState = root.querySelector('#cellular-sms-state');
		const smsControls = root.querySelector('#cellular-sms-inbox-controls');
		const smsOpen = root.querySelector('#cellular-sms-open');
		const smsClear = root.querySelector('#cellular-sms-clear');
		const smsOutput = root.querySelector('#cellular-sms-messages');
		const smsSearch = root.querySelector('#cellular-sms-search');
		const smsFilter = root.querySelector('#cellular-sms-filter');
		let smsSearchItems = [];
		function filterSms() {
			const query = smsSearch.value.trim().toLocaleLowerCase();
			const mode = smsFilter.value;
			let visible = 0;
			for (const item of smsSearchItems) {
				const match = (!query || item.search.includes(query)) &&
					(mode === 'all' || item.readState === mode);
				item.card.hidden = !match;
				if (match) visible++;
			}
			smsOutput.setAttribute('aria-label', visible+' of '+smsSearchItems.length+' SMS messages shown');
		}
		smsSearch.addEventListener('input', filterSms);
		smsFilter.addEventListener('change', filterSms);
		let smsEnabled = false;
		let smsGeneration = 0;
		function clearSms() {
			smsGeneration += 1;
			smsSearchItems = [];
			smsSearch.value = '';
			smsFilter.value = 'all';
			smsSearch.disabled = true;
			smsFilter.disabled = true;
			smsOutput.replaceChildren();
			smsOutput.textContent = 'No SMS loaded.';
		}
		function presentSmsSetting(enabled) {
			smsEnabled = enabled;
			smsToggle.checked = enabled;
			smsToggle.disabled = false;
			smsControls.hidden = !enabled;
			smsState.textContent = enabled ? 'SMS enabled' : 'SMS disabled — no messages can be read';
			if (!enabled) clearSms();
		}
		try {
			const settings = await api.call('veci.sms', 'getConfig', {}, { timeout: 4000 });
			if (settings?.ok !== true || typeof settings.enabled !== 'boolean')
				throw Error('SMS settings unavailable');
			presentSmsSetting(settings.enabled);
		} catch {
			smsToggle.disabled = true;
			smsControls.hidden = true;
			smsState.textContent = 'SMS settings unavailable for this account.';
		}
		smsToggle?.addEventListener('change', async () => {
			const desired = smsToggle.checked;
			smsToggle.disabled = true;
			// Invalidate in-flight rendering immediately when switching OFF.
			if (!desired) { smsEnabled = false; clearSms(); smsControls.hidden = true; }
			try {
				const result = await api.call('veci.sms', 'setEnabled',
					{ state: desired ? 'on' : 'off' }, { timeout: 5000 });
				if (result?.ok !== true || result.enabled !== desired)
					throw Error('Unable to update SMS setting');
				presentSmsSetting(desired);
				toast(desired ? 'SMS enabled.' : 'SMS disabled.', 'success');
			} catch {
				smsToggle.checked = !desired;
				smsState.textContent = 'Unable to change SMS setting. Refresh to verify.';
				smsToggle.disabled = false;
				// Keep any sensitive text cleared on ambiguous server result.
				if (!desired) smsControls.hidden = true;
				toast('Unable to change SMS setting.', 'warning');
			}
		});
		smsClear?.addEventListener('click', clearSms);
		smsOpen?.addEventListener('click', async () => {
			if (!smsEnabled) return;
			const turn = ++smsGeneration;
			setBusy(smsOpen, true, 'Loading Inbox…');
			smsOutput.replaceChildren();
			smsOutput.textContent = 'Loading SMS…';
			try {
				const result = await api.call('veci.sms', 'listMessages', {}, { timeout: 13000 });
				if (!smsEnabled || turn !== smsGeneration) return;
				const messages = result?.messages;
				if (result?.ok !== true || result.source !== 'on_demand_cmgl_pdu' ||
					!Number.isSafeInteger(result.count) || result.count < 0 || result.count > 16 ||
					!Array.isArray(messages) || messages.length !== result.count)
					throw Error('Invalid SMS response');
				const frag = document.createDocumentFragment();
				const head = document.createElement('p');
				head.textContent = 'Stored SMS: ' + result.count;
				frag.appendChild(head);
				const seen = new Set(), decodedRows=[];
				for(const item of messages) {
					if(!item || !Number.isSafeInteger(item.index) || item.index<0 ||
						item.index>65535 || seen.has(item.index) ||
						typeof item.pdu!=='string' || item.pdu.length>512)
						throw Error('Invalid SMS record');
					seen.add(item.index);
					let decoded=null,reason='';
					try { decoded=decodePrivatePdu(item.pdu); }
					catch(error){reason=String(error?.message||'Unknown').replace(/[^A-Za-z0-9 _-]/g,'').slice(0,42);}
					decodedRows.push({index:item.index,status:item.status,decoded,reason,pdu:item.pdu});
				}
				const storage=['SM','ME','MT'].includes(result.storage)?result.storage:'unknown';
				head.textContent+=' · Storage: '+(storage==='SM'?'SIM card':storage==='ME'?'Modem':storage==='MT'?'Combined':'Unknown');
				const rows=mergeSmsParts(decodedRows);
				rows.sort((a,b)=>(b.decoded?.received?.unixMs??-1)-(a.decoded?.received?.unixMs??-1));
				const statusName={0:'Unread',1:'Read',2:'Unsent',3:'Sent',4:'All'};
				const indexed = [];
				for(const item of rows) {
					const card=document.createElement('article');
					card.className='sms-message-card';
					card.style.cssText='border:1px solid #dce6ef;border-radius:12px;padding:14px 16px;margin:12px 0;background:#fff;overflow-wrap:anywhere;';
					const label=document.createElement('strong');
					label.style.cssText='display:block;font-size:14px;margin-bottom:6px;';
					const date=document.createElement('small');
					date.style.cssText='display:block;opacity:.78;margin-bottom:10px;';
					const body=document.createElement('p');
					body.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 12px;line-height:1.55;';
					const slotList=item.indices||[item.index];
					if(item.decoded){
						label.textContent='From: '+item.decoded.sender;
						date.textContent=formatSmsDate(item.decoded.received)+' · '+(statusName[item.status]||'Stored')+
						  ' · slot '+slotList.join(', ');
						body.textContent=item.decoded.text;
					}else{
						label.textContent='SMS slot '+item.index;
						date.textContent='Message metadata';
						body.textContent='Unable to decode SMS'+(item.reason?' ('+item.reason+')':'')+'.';
					}
					card.append(label,date,body);
					if((storage==='SM'||storage==='ME')&&item.decoded){
						const deleteBtn=document.createElement('button');
						deleteBtn.type='button';
						deleteBtn.className='button button-secondary';
						deleteBtn.textContent='Delete SMS';
						deleteBtn.addEventListener('click',async()=>{
							if(!smsEnabled || turn!==smsGeneration)return;
							const segments=(item.segments||[{index:item.index,pdu:item.pdu}])
							  .slice().sort((a,b)=>b.index-a.index);
							const labelStore=storage==='SM'?'SIM card':'modem';
							const confirmed=await confirm({
								title:'Permanently delete SMS?',
								message:'Delete this SMS from '+labelStore+' ('+segments.length+
								  ' stored segment(s))? This cannot be undone.',
								confirmLabel:'Delete permanently'
							});
							if(!confirmed||!smsEnabled||turn!==smsGeneration)return;
							setBusy(deleteBtn,true,'Deleting…');
							try{
								for(const part of segments){
									const response=await api.call('veci.sms','deleteMessage',{
										index:part.index,storage,expectedPdu:part.pdu
									},{timeout:12000});
									if(response?.ok!==true||response.deleted!==part.index||
										response.storage!==storage)throw Error('Delete not confirmed');
								}
								if(turn===smsGeneration){card.remove();toast('SMS deleted permanently.','success');}
							}catch{
								if(turn===smsGeneration)toast('Could not confirm SMS deletion. Reopen Inbox to refresh.','warning');
							}finally{setBusy(deleteBtn,false);}
						});
						deleteBtn.style.cssText='width:auto;min-width:110px;';
						card.append(deleteBtn);
					}
					// Native clipboard only on explicit click. Never transmit
					// or persist private SMS text beyond the rendered page.
					if(item.decoded){
						const copyBtn=document.createElement('button');
						copyBtn.type='button';
						copyBtn.className='button button-secondary';
						copyBtn.textContent='Copy message';
						copyBtn.style.cssText='width:auto;min-width:110px;margin-right:8px;';
						copyBtn.addEventListener('click',async()=>{
							if(!smsEnabled || turn!==smsGeneration)return;
							// HTTP://192.168.x.x is not a secure context, so most
							// browsers intentionally hide navigator.clipboard.
							// execCommand must be called synchronously during
							// the user gesture to retain clipboard permission.
							const legacyCopy=()=>{
								const field=document.createElement('textarea');
								const oldFocus=document.activeElement;
								field.value=item.decoded.text;
								field.readOnly=true;
								field.setAttribute('aria-hidden','true');
								field.style.cssText='position:fixed;left:-10000px;top:0;opacity:0;';
								document.body.appendChild(field);
								let ok=false;
								try{
									field.focus();
									field.select();
									ok=document.execCommand('copy')===true;
								}catch{}
								field.value='';
								field.remove();
								try{oldFocus?.focus({preventScroll:true});}catch{}
								return ok;
							};
							let copied=false;
							if(!window.isSecureContext || !navigator.clipboard?.writeText){
								copied=legacyCopy();
							}else{
								try{
									await navigator.clipboard.writeText(item.decoded.text);
									copied=true;
								}catch{
									// In secure contexts permission might be
									// rejected; do not report false success.
								}
							}
							if(copied){toast('SMS text copied.','success');return;}
							// A browser may block programmatic copying entirely.
							// Select visible text and let Ctrl+C work instead.
							try{
								const selection=window.getSelection();
								const range=document.createRange();
								range.selectNodeContents(body);
								selection.removeAllRanges();
								selection.addRange(range);
								toast('Select text ready — press Ctrl+C to copy.','warning');
							}catch{toast('Copy unavailable; select message text manually.','warning');}
						});
						card.append(copyBtn);
					}
					indexed.push({card,search:(item.decoded?.sender||'') .toLocaleLowerCase()+
						' '+(item.decoded?.text||'').toLocaleLowerCase(),
						readState:item.status===0?'unread':item.status===1?'read':'other'});
					frag.appendChild(card);
				}
				smsOutput.replaceChildren(frag);
				smsSearchItems = indexed;
				smsSearch.disabled = false;
				smsFilter.disabled = false;
				filterSms();
			} catch {
				if (smsEnabled && turn === smsGeneration) {
					smsOutput.textContent = 'Unable to load SMS Inbox.';
					toast('Could not load SMS. Please try again.', 'warning');
				}
			} finally {
				setBusy(smsOpen, false);
			}
		});

		const reconnect = root.querySelector('#cellular-reconnect');
		reconnect?.addEventListener('click', async () => {
			const ok = await confirm({
				title: 'Reconnect mobile data?',
				message: 'The cellular data session will be restarted. Internet access may drop briefly.',
				confirmLabel: 'Reconnect'
			});
			if (!ok) return;
			setBusy(reconnect, true, 'Reconnecting…');
			try {
				await api.cellularAction('reconnect');
				toast('Cellular reconnect requested.', 'success');
				setTimeout(() => this.render({ api, root, toast, confirm }), 1800);
			} catch (error) {
				toast(error.message || 'Reconnect failed.', 'error');
			} finally {
				setBusy(reconnect, false);
			}
		});

		const switchButton = root.querySelector('#cellular-switch-sim');
		switchButton?.addEventListener('click', async () => {
			const current = Number(status.sim) === 2 ? 2 : 1;
			const next = current === 1 ? 2 : 1;
			const ok = await confirm({
				title: `Switch to SIM ${next}?`,
				message:
					'The modem will change SIM and reconnect. This can interrupt Internet access for a short period.',
				confirmLabel: `Use SIM ${next}`
			});
			if (!ok) return;
			setBusy(switchButton, true, 'Switching…');
			try {
				await api.cellularAction('switchSim', { sim: next });
				toast(`Switch to SIM ${next} requested.`, 'success');
				setTimeout(() => this.render({ api, root, toast, confirm }), 2500);
			} catch (error) {
				toast(error.message || 'SIM switch failed.', 'error');
			} finally {
				setBusy(switchButton, false);
			}
		});
	}
};
