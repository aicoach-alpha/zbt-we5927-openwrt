import { badge, escapeHtml, setBusy } from '../lib/dom.js';
/* v1.6.1 staged candidate; DO NOT ship before atomic native CMGS + RPC + delivery store rollout. */

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


/* SMS-SUBMIT PDU for a SINGLE outbound message; no multipart sending.
 * Numbers only (alphanumeric senders such as XLPRIORITAS cannot be replied to).
 * Browser never persists or logs the SMS. No auto resend.
 */
function buildSmsSubmit(recipient, message) {
  if(typeof recipient!=='string' || !/^\+?[0-9]{3,15}$/.test(recipient))throw Error('Invalid recipient number');
  if(typeof message!=='string' || message.length===0 || message.length>160)throw Error('Message must fit one SMS');
  const base=[64,163,36,165,232,233,249,236,242,199,10,216,248,13,197,229,916,95,934,915,923,937,928,936,931,920,926,0,198,230,223,201,32,33,34,35,164,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,161,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,196,214,209,220,167,191,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,228,246,241,252,224];
  const glyphs=new Map(base.map((p,i)=>[p,i]).filter(([p])=>p!==0));
  const ext=new Map([[12,10],[94,20],[123,40],[125,41],[92,47],[91,60],[126,61],[93,62],[124,64],[8364,101]]);
  let septets=[],canGsm=true;
  for(const char of message) {
    const p=char.codePointAt(0);
    if(glyphs.has(p))septets.push(glyphs.get(p));
    else if(ext.has(p))septets.push(27,ext.get(p));
    else {canGsm=false;break;}
  }
  let dcs,udl,payload=[];
  if(canGsm) {
    if(septets.length<1 || septets.length>160)throw Error('SMS exceeds GSM7 single-message limit (160 septets)');
    dcs=0;udl=septets.length;
    payload=Array(Math.ceil(udl*7/8)).fill(0);
    septets.forEach((val,i)=>{
      for(let b=0;b<7;b++)if(val&(1<<b)){
        const bit=i*7+b;payload[bit>>3]|=1<<(bit&7);
      }
    });
  }else{
    // DCS 0x08, UTF-16BE: max 140 octets/70 UTF-16 code units.
    if(message.length>70)throw Error('Unicode SMS limit is 70 characters (UTF-16 code units)');
    dcs=8;udl=message.length*2;
    for(let i=0;i<message.length;i++){
      const v=message.charCodeAt(i);
      payload.push(v>>8,v&255);
    }
  }
  const digits=recipient[0]==='+'?recipient.slice(1):recipient;
  const addr=[];
  for(let i=0;i<digits.length;i+=2){
    const low=Number(digits[i]),high=i+1<digits.length?Number(digits[i+1]):15;
    addr.push(low|(high<<4));
  }
  const bytes=[0,1,0,digits.length,recipient[0]==='+'?0x91:0x81,
    ...addr,0,dcs,udl,...payload];
  if(bytes.length>192)throw Error('Message exceeds modem SMS limit');
  return bytes.map(b=>b.toString(16).padStart(2,'0')).join('').toUpperCase();
}



/* One user-approved multipart SMS transaction. Individual modem submissions
 * are carried by the existing authenticated sendMessage RPC, in sequence.
 * A segment uses 8-bit concat UDH 05 00 03 ref total part. Never auto-retry
 * after failure or uncertain delivery, because parts may already be sent.
 * v1.6.0 supports at most four segments: 4x153 GSM7 / 4x67 UCS2 units.
 */
function buildSmsSubmitSegments(recipient, message, reference=1) {
  if(typeof recipient!=='string'|| !/^\+?[0-9]{3,15}$/.test(recipient))
    throw Error('Invalid recipient number');
  if(typeof message!=='string'||message.length===0||message.length>612)
    throw Error('Message must be 1–612 characters');
  if(!Number.isInteger(reference)||reference<1||reference>255)
    throw Error('Invalid SMS concatenation reference');
  const map=[64,163,36,165,232,233,249,236,242,199,10,216,248,13,197,229,916,95,934,915,923,937,928,936,931,920,926,0,198,230,223,201,32,33,34,35,164,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,161,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,196,214,209,220,167,191,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,228,246,241,252,224];
  const basic=new Map(map.map((p,i)=>[p,i]).filter(([p])=>p!==0));
  const ext=new Map([[12,10],[94,20],[123,40],[125,41],[92,47],[91,60],[126,61],[93,62],[124,64],[8364,101]]);
  const chars=[];
  let gsm=true,septetCount=0;
  for(const char of message) {
    const cp=char.codePointAt(0);
    if(basic.has(cp)){chars.push({str:char,codes:[basic.get(cp)]});septetCount++;}
    else if(ext.has(cp)){chars.push({str:char,codes:[27,ext.get(cp)]});septetCount+=2;}
    else {gsm=false;break;}
  }
  if(gsm && septetCount<=160)return [buildSmsSubmit(recipient,message)];
  if(!gsm && message.length<=70)return [buildSmsSubmit(recipient,message)];
  const digits=recipient.startsWith('+')?recipient.slice(1):recipient;
  const addr=[];
  for(let i=0;i<digits.length;i+=2){
    addr.push(Number(digits[i])|((i+1<digits.length?Number(digits[i+1]):15)<<4));
  }
  const base=[0,0x41,0,digits.length,recipient.startsWith('+')?0x91:0x81,...addr,0,gsm?0:8];
  const chunks=[];
  if(gsm){
    let chunk=[],length=0;
    for(const value of chars){
      if(length+value.codes.length>153){chunks.push(chunk);chunk=[];length=0;}
      chunk.push(...value.codes);length+=value.codes.length;
    }
    if(chunk.length)chunks.push(chunk);
  }else{
    if(message.length>268)throw Error('Unicode multipart limit is 268 UTF-16 units');
    let chunk='';
    for(const ch of message){
      if(chunk.length+ch.length>67){chunks.push(chunk);chunk='';}
      chunk+=ch;
    }
    if(chunk)chunks.push(chunk);
  }
  if(chunks.length<2||chunks.length>4)throw Error('SMS exceeds four-part message limit');
  return chunks.map((chunk,i)=>{
    const udh=[5,0,3,reference,chunks.length,i+1];
    let payload,udl;
    if(gsm){
      // UDH spans 6 octets, equal to 7 septets including 1 fill bit.
      udl=7+chunk.length;
      payload=Array(Math.ceil(udl*7/8)).fill(0);
      udh.forEach((v,j)=>{payload[j]=v;});
      chunk.forEach((value,j)=>{
        for(let b=0;b<7;b++)if(value&(1<<b)){
          const pos=(7+j)*7+b;
          payload[pos>>3]|=1<<(pos&7);
        }
      });
    }else{
      payload=[...udh];
      for(let j=0;j<chunk.length;j++){
        const cp=chunk.charCodeAt(j);
        payload.push(cp>>8,cp&255);
      }
      udl=payload.length;
    }
    if(payload.length>140||udl>160)throw Error('SMS segment exceeds modem limit');
    const all=[...base,udl,...payload];
    return all.map(v=>v.toString(16).padStart(2,'0')).join('').toUpperCase();
  });
}

/* v1.6.1, applied only after explicit Send confirmation.
 * Legacy drafts remain unchanged; request SRR per submitted segment.
 */
function requestSmsDeliveryReport(pdu) {
  if(typeof pdu!=='string' || !/^00(?:01|41)(?:[0-9A-F]{2}){9,190}$/.test(pdu))
    throw Error('Invalid outbound SMS PDU');
  const octet=pdu.slice(2,4);
  return '00'+(octet==='01'?'21':'61')+pdu.slice(4);
}

/* Decode only locally-saved, successful outgoing SMS-SUBMIT PDUs.
 * No re-fetch from modem, no network requests or browser persistence. */
function decodeSentPdu(hex) {
  if(typeof hex!=='string'||! /^(?:[0-9A-F]{2}){11,192}$/.test(hex))
    throw Error('Invalid Sent PDU');
  const b=Uint8Array.from(hex.match(/../g),h=>parseInt(h,16));
  if(b[0]!==0||![1,0x21,0x41,0x61].includes(b[1])||b[2]!==0)
    throw Error('Unsupported Submit PDU');
  const multipart=(b[1]&0x40)!==0;
  const count=b[3],toa=b[4];
  if(count<3||count>15||(toa!==0x81&&toa!==0x91))throw Error('Recipient');
  let to=toa===0x91?'+':'';
  for(let i=0;i<count;i++){
    const v=(i&1)?(b[5+(i>>1)]>>4):(b[5+(i>>1)]&15);
    if(v>9)throw Error('Invalid recipient');
    to+=v;
  }
  const at=5+Math.ceil(count/2);
  if(at+3>b.length||b[at]!==0)throw Error('Submit header');
  const dcs=b[at+1],len=b[at+2],data=b.slice(at+3);
  let concat=null;
  if(multipart){
    if(data.length<7 || data[0]!==5 || data[1]!==0 || data[2]!==3)
      throw Error('Unsupported multipart header');
    if(data[4]<2||data[4]>10||data[5]<1||data[5]>data[4])
      throw Error('Invalid multipart sequencing');
    concat={ref:data[3],total:data[4],part:data[5]};
  }
  let text='';
  if(dcs===0){
    if(len>160||len<(multipart?8:1)||data.length!==Math.ceil(len*7/8))throw Error('GSM7 length');
    const base=[64,163,36,165,232,233,249,236,242,199,10,216,248,13,197,229,916,95,934,915,923,937,928,936,931,920,926,0,198,230,223,201,32,33,34,35,164,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,161,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,196,214,209,220,167,191,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,228,246,241,252,224];
    const ext={10:12,20:94,40:123,41:125,47:92,60:91,61:126,62:93,64:124,101:8364};
    let esc=false;
    for(let i=multipart?7:0;i<len;i++){
      const bit=i*7,byte=bit>>3,shift=bit&7;
      const septet=((data[byte]>>shift)|((data[byte+1]||0)<<(8-shift)))&127;
      if(esc){if(ext[septet]===undefined)throw Error('Invalid extension');text+=String.fromCodePoint(ext[septet]);esc=false;}
      else if(septet===27)esc=true;
      else {if(!base[septet])throw Error('Invalid GSM7');text+=String.fromCodePoint(base[septet]);}
    }
    if(esc)throw Error('Invalid extension');
  }else if(dcs===8){
    if(len<(multipart?8:2)||len>140||
       (multipart?(len-6)%2:len%2)||data.length!==len)throw Error('UCS2 length');
    for(let i=multipart?6:0;i<len;i+=2)
      text+=String.fromCharCode((data[i]<<8)|data[i+1]);
  }else throw Error('Unsupported alphabet');
  return {to,text,concat};
}

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

		// The router's Content-Security-Policy is style-src 'self'.
		// Inline <style> and style="..." are blocked; load a local CSS file.
		// Keep a single stylesheet when navigating away/back to Cellular.
		if (!document.getElementById('veci-sms-center-v159-css')) {
			const link = document.createElement('link');
			link.id = 'veci-sms-center-v159-css';
			link.rel = 'stylesheet';
			link.href = '/veci/sms-center.css?v=159';
			document.head.appendChild(link);
		}

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
						<button class="button button-secondary" id="cellular-sms-compose-open" type="button">Compose SMS</button>
						<button class="button button-secondary" id="cellular-sms-sent-open" type="button">Sent Messages</button>
						<button class="button button-secondary" id="cellular-sms-drafts-open" type="button">Drafts</button>
					</div>
					<form id="cellular-sms-compose" hidden autocomplete="off" aria-label="Compose SMS">
						<div>
							<strong class="sms-compose-title">New message</strong>
							<p class="sms-compose-subtitle">Compose an SMS using the currently active SIM card.</p>
						</div>
						<label class="sms-compose-field" for="cellular-sms-to">Recipient number
							<input id="cellular-sms-to" type="tel" inputmode="tel" placeholder="+628123456789" autocomplete="off" required pattern="\\+?[0-9]{3,15}" />
						</label>
						<label class="sms-compose-field" for="cellular-sms-text">Message
							<textarea id="cellular-sms-text" maxlength="612" rows="5" required placeholder="Write your message here…"></textarea>
						</label>
						<p id="cellular-sms-length" aria-live="polite">Up to 4 SMS parts · 153 GSM7 or 67 Unicode units per multipart segment</p>
						<p id="cellular-sms-send-status" role="status" aria-live="polite">Not sent.</p>
						<div class="sms-compose-actions">
							<button class="button" id="cellular-sms-send" type="submit">Send SMS</button>
							<button class="button button-secondary" id="cellular-sms-draft-save" type="button">Save Draft</button>
							<button class="button button-secondary" id="cellular-sms-compose-close" type="button">Close</button>
						</div>
					</form>
					<div id="cellular-sms-drafts-panel" hidden style="border:1px solid #dce6ef;border-radius:12px;padding:14px 16px;margin:12px 0">
						<strong>Drafts</strong>
						<p id="cellular-sms-drafts-status" role="status">Open Drafts to load saved messages. Up to 10 drafts.</p>
						<div id="cellular-sms-drafts-list"></div>
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
					<div id="cellular-sms-sent-panel" hidden style="margin-top:16px;border-top:1px solid #dce6ef;padding-top:14px">
						<strong>Sent Messages</strong>
						<p>Messages accepted by the modem and saved on this router. Delivery to recipient is not guaranteed by this status.</p>
						<div id="cellular-sms-sent-messages" role="status" aria-live="polite">Open Sent Messages to view history.</div>
					</div>
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
		const smsSentOpen = root.querySelector('#cellular-sms-sent-open');
		const smsSentPanel = root.querySelector('#cellular-sms-sent-panel');
		const smsSentOutput = root.querySelector('#cellular-sms-sent-messages');
		let smsSentGeneration = 0;
		function clearSent() {
			smsSentGeneration++;
			smsSentOutput.replaceChildren();
			smsSentOutput.textContent='No Sent Messages loaded.';
			smsSentPanel.hidden=true;
		}
		const smsComposeOpen = root.querySelector('#cellular-sms-compose-open');
		const smsCompose = root.querySelector('#cellular-sms-compose');
		const smsTo = root.querySelector('#cellular-sms-to');
		const smsText = root.querySelector('#cellular-sms-text');
		const smsLength = root.querySelector('#cellular-sms-length');
		const smsSendStatus = root.querySelector('#cellular-sms-send-status');
		const smsSend = root.querySelector('#cellular-sms-send');
		const smsComposeClose = root.querySelector('#cellular-sms-compose-close');
		const smsDraftOpen = root.querySelector('#cellular-sms-drafts-open');
		const smsDraftSave = root.querySelector('#cellular-sms-draft-save');
		const smsDraftPanel = root.querySelector('#cellular-sms-drafts-panel');
		const smsDraftStatus = root.querySelector('#cellular-sms-drafts-status');
		const smsDraftList = root.querySelector('#cellular-sms-drafts-list');
		let selectedDraft=null;
		let draftGeneration=0;
		function clearDrafts(){
			draftGeneration++;
			selectedDraft=null;
			smsDraftSave.textContent='Save Draft';
			smsDraftList.replaceChildren();
			smsDraftPanel.hidden=true;
		}
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
			clearDrafts();
			smsSearchItems = [];
			smsSearch.value = '';
			smsFilter.value = 'all';
			smsSearch.disabled = true;
			smsFilter.disabled = true;
			smsOutput.replaceChildren();
			smsOutput.textContent = 'No SMS loaded.';
			clearSent();
		}
		function presentSmsSetting(enabled) {
			smsEnabled = enabled;
			smsToggle.checked = enabled;
			smsToggle.disabled = false;
			smsControls.hidden = !enabled;
			smsState.textContent = enabled ? 'SMS enabled' : 'SMS disabled — no messages can be read';
			if (!enabled) {
				clearSms();
				smsCompose.hidden=true;
				smsText.value='';
				smsTo.value='';
				smsSendStatus.textContent='Not sent.';
			}
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
		const openCompose = (number='')=>{
			if(!smsEnabled)return;
			selectedDraft=null;
			smsDraftSave.textContent='Save Draft';
			smsCompose.hidden=false;
			if(number)smsTo.value=number;
			smsTo.focus();
		};
		smsComposeOpen.addEventListener('click',()=>openCompose());
		smsSentOpen.addEventListener('click',async()=>{
			if(!smsEnabled)return;
			const turn=++smsSentGeneration;
			smsSentPanel.hidden=false;
			smsSentOutput.replaceChildren();
			smsSentOutput.textContent='Loading Sent Messages…';
			setBusy(smsSentOpen,true,'Loading…');
			try{
				const result=await api.call('veci.sms','getSent',{}, {timeout:6000});
				if(!smsEnabled||turn!==smsSentGeneration)return;
				if(result?.ok!==true||result.source!=='local_sent'||
				   !Number.isSafeInteger(result.count)||result.count<0||result.count>30||
				   !Array.isArray(result.messages)||result.messages.length!==result.count)
					throw Error('Invalid Sent data');
				const fragment=document.createDocumentFragment();
				if(!result.count){
					const p=document.createElement('p');
					p.textContent='No saved outgoing SMS yet. Only messages sent after Sent History is enabled will appear here.';
					fragment.appendChild(p);
				}
				for(const record of result.messages){
					if(!Number.isSafeInteger(record.at)||record.at<1000000000||
					   record.status!=='accepted_by_modem')throw Error('Invalid Sent entry');
					const deliveryStates={
					  unconfirmed:'Delivery unconfirmed',
					  awaiting_report:'Awaiting operator report',
					  pending:'Delivery pending (operator report)',
					  delivered:'Delivered (operator report)',
					  failed:'Delivery failed (operator report)',
					  unknown:'Delivery status unknown'
					};
					const state=record.delivery_status??'unconfirmed';
					if(!Object.hasOwn(deliveryStates,state))throw Error('Invalid delivery state');
					const decoded=decodeSentPdu(record.pdu);
					const card=document.createElement('article');
					card.className='sms-message-card';
					card.style.cssText='border:1px solid #dce6ef;border-radius:12px;padding:14px 16px;margin:10px 0;background:#fff;overflow-wrap:anywhere;';
					const to=document.createElement('strong');
					to.textContent='To: '+decoded.to;
					const meta=document.createElement('small');
					meta.style.cssText='display:block;opacity:.8;margin:5px 0 10px;';
					meta.textContent=new Date(record.at*1000).toLocaleString('id-ID')+
					  ' · '+deliveryStates[state] +
					  (decoded.concat?' · SMS part '+decoded.concat.part+'/'+decoded.concat.total:'');
					const body=document.createElement('p');
					body.textContent=decoded.text;
					body.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;margin:0;';
					card.append(to,meta,body);
					fragment.append(card);
				}
				smsSentOutput.replaceChildren(fragment);
			}catch{
				if(turn===smsSentGeneration && smsEnabled)
					smsSentOutput.textContent='Unable to load Sent Messages. Please try again.';
			}finally{setBusy(smsSentOpen,false);}
		});


		async function renderDrafts(){
			if(!smsEnabled)return;
			const turn=++draftGeneration;
			smsDraftPanel.hidden=false;
			smsDraftStatus.textContent='Loading Drafts…';
			smsDraftList.replaceChildren();
			setBusy(smsDraftOpen,true,'Loading…');
			try{
				const r=await api.call('veci.sms','getDrafts',{}, {timeout:6000});
				if(!smsEnabled || turn!==draftGeneration)return;
				if(r?.ok!==true||r.source!=='local_drafts' ||
					!Number.isSafeInteger(r.count)||r.count<0||r.count>10 ||
					!Array.isArray(r.drafts)||r.drafts.length!==r.count)
					throw Error('Invalid draft listing');
				const frag=document.createDocumentFragment();
				const seen=new Set();
				for(const item of r.drafts){
					if(!Number.isSafeInteger(item.id)||item.id<1||item.id>10 ||
						seen.has(item.id)||!Number.isSafeInteger(item.at)||
						item.at<0||typeof item.pdu!=='string'||item.pdu.length>384)
						throw Error('Invalid draft entry');
					seen.add(item.id);
					const decoded=decodeSentPdu(item.pdu);
					const card=document.createElement('article');
					card.style.cssText='border:1px solid #dce6ef;border-radius:12px;padding:12px;margin:10px 0;overflow-wrap:anywhere;';
					const title=document.createElement('strong');
					title.textContent='To: '+decoded.to;
					const date=document.createElement('small');
					date.style.cssText='display:block;opacity:.78;margin:6px 0';
					date.textContent=new Date(item.at*1000).toLocaleString('id-ID')+' · Unsent draft';
					const body=document.createElement('p');
					body.textContent=decoded.text;
					body.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';
					const edit=document.createElement('button');
					edit.type='button';edit.className='button button-secondary';
					edit.textContent='Edit Draft';
					edit.addEventListener('click',()=>{
						if(!smsEnabled || turn!==draftGeneration)return;
						openCompose(decoded.to);
						smsText.value=decoded.text;
						selectedDraft={id:item.id,original:item.pdu};
						smsDraftSave.textContent='Update Draft';
						smsSendStatus.textContent='Editing saved draft. Not sent.';
					});
					const del=document.createElement('button');
					del.type='button';del.className='button button-secondary';
					del.textContent='Delete Draft';
					del.style.cssText='margin-left:8px';
					del.addEventListener('click',async()=>{
						if(!smsEnabled || turn!==draftGeneration)return;
						const yes=await confirm({
							title:'Delete this draft?',
							message:'Remove this unsent draft from router storage? This cannot be undone.',
							confirmLabel:'Delete Draft'
						});
						if(!yes || !smsEnabled || turn!==draftGeneration)return;
						setBusy(del,true,'Deleting…');
						try{
							const result=await api.call('veci.sms','deleteDraft',
								{id:item.id,expectedPdu:item.pdu},{timeout:6500});
							if(result?.ok!==true || result.deleted!==item.id)throw Error('Delete unsuccessful');
							if(selectedDraft?.id===item.id){
								selectedDraft=null;smsDraftSave.textContent='Save Draft';
							}
							toast('Draft deleted.','success');
							await renderDrafts();
						}catch{smsDraftStatus.textContent='Draft deletion failed; refresh list before retrying.';}
						finally{setBusy(del,false);}
					});
					card.append(title,date,body,edit,del);
					frag.appendChild(card);
				}
				smsDraftList.replaceChildren(frag);
				smsDraftStatus.textContent=r.count+
					' saved drafts on this router. Only valid single-SMS drafts can be saved.';
			}catch{
				if(turn===draftGeneration)smsDraftStatus.textContent='Could not load Drafts. Inbox and Sent are unchanged.';
			}finally{setBusy(smsDraftOpen,false);}
		}
		smsDraftOpen.addEventListener('click',renderDrafts);
		smsDraftSave.addEventListener('click',async()=>{
			if(!smsEnabled || smsDraftSave.disabled)return;
			let pdu;
			try{pdu=buildSmsSubmit(smsTo.value.trim(),smsText.value);}
			catch(e){smsSendStatus.textContent='Draft not saved: '+String(e?.message||'Invalid message');return;}
			const saved=selectedDraft;
			setBusy(smsDraftSave,true,'Saving…');
			try{
				const r=await api.call('veci.sms','saveDraft',{
					id:saved?.id??0,expectedPdu:saved?.original??'-',pdu
				},{timeout:6500});
				if(r?.ok!==true || r.saved!==true ||
					!Number.isSafeInteger(r.id)||r.id<1||r.id>10)throw Error('Draft save failed');
				selectedDraft={id:r.id,original:pdu};
				smsDraftSave.textContent='Update Draft';
				smsSendStatus.textContent='Draft saved on the router. It has not been sent.';
				toast('Draft saved.','success');
				await renderDrafts();
			}catch{smsSendStatus.textContent='Draft not saved. Check storage or reopen Drafts before retrying.';}
			finally{setBusy(smsDraftSave,false);}
		});

		smsComposeClose.addEventListener('click',()=>{
			smsCompose.hidden=true;
			smsSendStatus.textContent='Not sent.';
		});
		smsText.addEventListener('input',()=>{
			try{
				if(!smsText.value){smsLength.textContent='Up to 4 SMS parts · 153 GSM7 or 67 Unicode units per multipart segment';return;}
				const parts=buildSmsSubmitSegments(smsTo.value||'+628123456789',smsText.value,1);
				smsLength.textContent=smsText.value.length+' characters · '+parts.length+
					(parts.length===1?' SMS':' SMS parts')+' · Carrier may charge per part';
			}catch(e){
				smsLength.textContent=String(e?.message||'Message limit exceeded');
			}
		});
		smsCompose.addEventListener('submit',async(event)=>{
			event.preventDefault();
			if(!smsEnabled || smsSend.disabled)return;
			const recipient=smsTo.value.trim(),message=smsText.value;
			let plan;
			try{plan=buildSmsSubmitSegments(recipient,message,1);}
			catch(e){smsSendStatus.textContent=String(e?.message||'Invalid SMS');return;}
			const count=plan.length;
			const approved=await confirm({
				title:'Send '+count+' SMS '+(count===1?'part':'parts')+' to '+recipient+'?',
				message:'Send this message using the active SIM? '+count+
					' SMS submission(s) may be billed. If an outcome is uncertain, VeCI will stop instead of retrying.',
				confirmLabel:'Send SMS'
			});
			if(!approved || !smsEnabled)return;
			const reference=window.crypto?.getRandomValues
				? (window.crypto.getRandomValues(new Uint8Array(1))[0]||1)
				: (1+Math.floor(Math.random()*255));
			try{plan=buildSmsSubmitSegments(recipient,message,reference).map(requestSmsDeliveryReport);}
			catch{smsSendStatus.textContent='Could not prepare SMS segments.';return;}
			setBusy(smsSend,true,'Sending…');
			smsTo.disabled=true;smsText.disabled=true;
			smsComposeClose.disabled=true;smsDraftSave.disabled=true;
			let accepted=0,historyMissing=false,trackingMissing=false,failure='';
			try{
				for(let i=0;i<plan.length;i++){
					if(!smsEnabled){failure='SMS was disabled; remaining parts not sent.';break;}
					if(i>0){
						// Existing backend enforces 5s between separate modem submissions.
						// This is the next planned part, NOT a retry of the prior part.
						smsSendStatus.textContent=accepted+'/'+count+' parts accepted. Waiting to send next part…';
						await new Promise(resolve=>setTimeout(resolve,5300));
						if(!smsEnabled){failure='SMS was disabled; remaining parts not sent.';break;}
					}
					smsSendStatus.textContent='Sending SMS part '+(i+1)+'/'+count+'…';
					let r;
					try{r=await api.call('veci.sms','sendMessage',{pdu:plan[i]},{timeout:46000});}
					catch{failure='Outcome unknown for part '+(i+1)+'/'+count+'. No automatic retry.';break;}
					if(r?.ok===true && r.status==='accepted_by_modem'){
						accepted++;
						if(r.history_saved===false)historyMissing=true;
						if(r.delivery_tracking===false)trackingMissing=true;
						smsSendStatus.textContent=accepted+'/'+count+' SMS parts accepted by modem.';
					}else{
						failure=(r?.reason==='network_rejected'?'Modem/network rejected':
							r?.reason==='send_rate_limited'?'Rate-limited':'Outcome unknown for')+
							' part '+(i+1)+'/'+count+'. Do not automatically resend.';
						break;
					}
				}
				if(accepted===count){
					smsSendStatus.textContent='All '+count+' part(s) accepted by modem. '+(historyMissing?
						'Some Sent records could not be saved. ':'')+(trackingMissing?
						'Some delivery reports cannot be tracked. ':'')+'Delivery to recipient is not yet confirmed.';
					smsText.value='';
					smsLength.textContent='Up to 4 SMS parts · 153 GSM7 or 67 Unicode units per multipart segment';
					toast('SMS accepted by modem ('+count+' part(s)).','success');
				}else{
					smsSendStatus.textContent=accepted+'/'+count+' parts confirmed accepted. '+failure+
						' Other parts may already have arrived. Check the recipient before attempting a new message.';
				}
			}finally{
				plan=null;
				smsTo.disabled=false;smsText.disabled=false;
				smsComposeClose.disabled=false;smsDraftSave.disabled=false;
				setBusy(smsSend,false);
			}
		});
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
					// Reply is only possible if sender is a real phone number.
					if(item.decoded && /^\\+?[0-9]{3,15}$/.test(item.decoded.sender)){
						const replyBtn=document.createElement('button');
						replyBtn.type='button';
						replyBtn.className='button button-secondary';
						replyBtn.style.cssText='width:auto;margin-right:8px;';
						replyBtn.textContent='Reply';
						replyBtn.addEventListener('click',()=>{
							if(smsEnabled && turn===smsGeneration)openCompose(item.decoded.sender);
						});
						card.append(replyBtn);
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
