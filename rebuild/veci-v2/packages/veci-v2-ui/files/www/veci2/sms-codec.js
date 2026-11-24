/* VeCI v2 SMS codec: migrated from reviewed v1 SMS PDU functions.
 * Pure client-side functions, no AT side effects or local persistence.
 * Single owner of v2 PDU codec; do not import vendor binaries.
 */
;(function () {
"use strict";
function buildSmsSubmit(recipient, message) {
	if (typeof recipient !== 'string' || !/^\+?[0-9]{3,15}$/.test(recipient)) throw Error('Invalid recipient number');
	if (typeof message !== 'string' || message.length === 0 || message.length > 160)
		throw Error('Message must fit one SMS');
	const base = [
		64, 163, 36, 165, 232, 233, 249, 236, 242, 199, 10, 216, 248, 13, 197, 229, 916, 95, 934, 915, 923, 937, 928,
		936, 931, 920, 926, 0, 198, 230, 223, 201, 32, 33, 34, 35, 164, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
		49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 161, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76,
		77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 196, 214, 209, 220, 167, 191, 97, 98, 99, 100, 101, 102,
		103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 228, 246,
		241, 252, 224
	];
	const glyphs = new Map(base.map((p, i) => [p, i]).filter(([p]) => p !== 0));
	const ext = new Map([
		[12, 10],
		[94, 20],
		[123, 40],
		[125, 41],
		[92, 47],
		[91, 60],
		[126, 61],
		[93, 62],
		[124, 64],
		[8364, 101]
	]);
	let septets = [],
		canGsm = true;
	for (const char of message) {
		const p = char.codePointAt(0);
		if (glyphs.has(p)) septets.push(glyphs.get(p));
		else if (ext.has(p)) septets.push(27, ext.get(p));
		else {
			canGsm = false;
			break;
		}
	}
	let dcs,
		udl,
		payload = [];
	if (canGsm) {
		if (septets.length < 1 || septets.length > 160)
			throw Error('SMS exceeds GSM7 single-message limit (160 septets)');
		dcs = 0;
		udl = septets.length;
		payload = Array(Math.ceil((udl * 7) / 8)).fill(0);
		septets.forEach((val, i) => {
			for (let b = 0; b < 7; b++)
				if (val & (1 << b)) {
					const bit = i * 7 + b;
					payload[bit >> 3] |= 1 << (bit & 7);
				}
		});
	} else {
		// DCS 0x08, UTF-16BE: max 140 octets/70 UTF-16 code units.
		if (message.length > 70) throw Error('Unicode SMS limit is 70 characters (UTF-16 code units)');
		dcs = 8;
		udl = message.length * 2;
		for (let i = 0; i < message.length; i++) {
			const v = message.charCodeAt(i);
			payload.push(v >> 8, v & 255);
		}
	}
	const digits = recipient[0] === '+' ? recipient.slice(1) : recipient;
	const addr = [];
	for (let i = 0; i < digits.length; i += 2) {
		const low = Number(digits[i]),
			high = i + 1 < digits.length ? Number(digits[i + 1]) : 15;
		addr.push(low | (high << 4));
	}
	const bytes = [0, 1, 0, digits.length, recipient[0] === '+' ? 0x91 : 0x81, ...addr, 0, dcs, udl, ...payload];
	if (bytes.length > 192) throw Error('Message exceeds modem SMS limit');
	return bytes
		.map(b => b.toString(16).padStart(2, '0'))
		.join('')
		.toUpperCase();
}

/* One user-approved multipart SMS transaction. Individual modem submissions
 * are carried by the existing authenticated sendMessage RPC, in sequence.
 * A segment uses 8-bit concat UDH 05 00 03 ref total part. Never auto-retry
 * after failure or uncertain delivery, because parts may already be sent.
 * v1.6.0 supports at most four segments: 4x153 GSM7 / 4x67 UCS2 units.
 */
function buildSmsSubmitSegments(recipient, message, reference = 1) {
	if (typeof recipient !== 'string' || !/^\+?[0-9]{3,15}$/.test(recipient)) throw Error('Invalid recipient number');
	if (typeof message !== 'string' || message.length === 0 || message.length > 612)
		throw Error('Message must be 1–612 characters');
	if (!Number.isInteger(reference) || reference < 1 || reference > 255)
		throw Error('Invalid SMS concatenation reference');
	const map = [
		64, 163, 36, 165, 232, 233, 249, 236, 242, 199, 10, 216, 248, 13, 197, 229, 916, 95, 934, 915, 923, 937, 928,
		936, 931, 920, 926, 0, 198, 230, 223, 201, 32, 33, 34, 35, 164, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
		49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 161, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76,
		77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 196, 214, 209, 220, 167, 191, 97, 98, 99, 100, 101, 102,
		103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 228, 246,
		241, 252, 224
	];
	const basic = new Map(map.map((p, i) => [p, i]).filter(([p]) => p !== 0));
	const ext = new Map([
		[12, 10],
		[94, 20],
		[123, 40],
		[125, 41],
		[92, 47],
		[91, 60],
		[126, 61],
		[93, 62],
		[124, 64],
		[8364, 101]
	]);
	const chars = [];
	let gsm = true,
		septetCount = 0;
	for (const char of message) {
		const cp = char.codePointAt(0);
		if (basic.has(cp)) {
			chars.push({ str: char, codes: [basic.get(cp)] });
			septetCount++;
		} else if (ext.has(cp)) {
			chars.push({ str: char, codes: [27, ext.get(cp)] });
			septetCount += 2;
		} else {
			gsm = false;
			break;
		}
	}
	if (gsm && septetCount <= 160) return [buildSmsSubmit(recipient, message)];
	if (!gsm && message.length <= 70) return [buildSmsSubmit(recipient, message)];
	const digits = recipient.startsWith('+') ? recipient.slice(1) : recipient;
	const addr = [];
	for (let i = 0; i < digits.length; i += 2) {
		addr.push(Number(digits[i]) | ((i + 1 < digits.length ? Number(digits[i + 1]) : 15) << 4));
	}
	const base = [0, 0x41, 0, digits.length, recipient.startsWith('+') ? 0x91 : 0x81, ...addr, 0, gsm ? 0 : 8];
	const chunks = [];
	if (gsm) {
		let chunk = [],
			length = 0;
		for (const value of chars) {
			if (length + value.codes.length > 153) {
				chunks.push(chunk);
				chunk = [];
				length = 0;
			}
			chunk.push(...value.codes);
			length += value.codes.length;
		}
		if (chunk.length) chunks.push(chunk);
	} else {
		if (message.length > 268) throw Error('Unicode multipart limit is 268 UTF-16 units');
		let chunk = '';
		for (const ch of message) {
			if (chunk.length + ch.length > 67) {
				chunks.push(chunk);
				chunk = '';
			}
			chunk += ch;
		}
		if (chunk) chunks.push(chunk);
	}
	if (chunks.length < 2 || chunks.length > 4) throw Error('SMS exceeds four-part message limit');
	return chunks.map((chunk, i) => {
		const udh = [5, 0, 3, reference, chunks.length, i + 1];
		let payload, udl;
		if (gsm) {
			// UDH spans 6 octets, equal to 7 septets including 1 fill bit.
			udl = 7 + chunk.length;
			payload = Array(Math.ceil((udl * 7) / 8)).fill(0);
			udh.forEach((v, j) => {
				payload[j] = v;
			});
			chunk.forEach((value, j) => {
				for (let b = 0; b < 7; b++)
					if (value & (1 << b)) {
						const pos = (7 + j) * 7 + b;
						payload[pos >> 3] |= 1 << (pos & 7);
					}
			});
		} else {
			payload = [...udh];
			for (let j = 0; j < chunk.length; j++) {
				const cp = chunk.charCodeAt(j);
				payload.push(cp >> 8, cp & 255);
			}
			udl = payload.length;
		}
		if (payload.length > 140 || udl > 160) throw Error('SMS segment exceeds modem limit');
		const all = [...base, udl, ...payload];
		return all
			.map(v => v.toString(16).padStart(2, '0'))
			.join('')
			.toUpperCase();
	});
}

/* Decode only locally-saved, successful outgoing SMS-SUBMIT PDUs.
 * No re-fetch from modem, no network requests or browser persistence. */
function decodeSentPdu(hex) {
	if (typeof hex !== 'string' || !/^(?:[0-9A-F]{2}){11,192}$/.test(hex)) throw Error('Invalid Sent PDU');
	const b = Uint8Array.from(hex.match(/../g), h => parseInt(h, 16));
	if (b[0] !== 0 || (b[1] !== 1 && b[1] !== 0x41) || b[2] !== 0) throw Error('Unsupported Submit PDU');
	const multipart = b[1] === 0x41;
	const count = b[3],
		toa = b[4];
	if (count < 3 || count > 15 || (toa !== 0x81 && toa !== 0x91)) throw Error('Recipient');
	let to = toa === 0x91 ? '+' : '';
	for (let i = 0; i < count; i++) {
		const v = i & 1 ? b[5 + (i >> 1)] >> 4 : b[5 + (i >> 1)] & 15;
		if (v > 9) throw Error('Invalid recipient');
		to += v;
	}
	const at = 5 + Math.ceil(count / 2);
	if (at + 3 > b.length || b[at] !== 0) throw Error('Submit header');
	const dcs = b[at + 1],
		len = b[at + 2],
		data = b.slice(at + 3);
	let concat = null;
	if (multipart) {
		if (data.length < 7 || data[0] !== 5 || data[1] !== 0 || data[2] !== 3)
			throw Error('Unsupported multipart header');
		if (data[4] < 2 || data[4] > 10 || data[5] < 1 || data[5] > data[4])
			throw Error('Invalid multipart sequencing');
		concat = { ref: data[3], total: data[4], part: data[5] };
	}
	let text = '';
	if (dcs === 0) {
		if (len > 160 || len < (multipart ? 8 : 1) || data.length !== Math.ceil((len * 7) / 8))
			throw Error('GSM7 length');
		const base = [
			64, 163, 36, 165, 232, 233, 249, 236, 242, 199, 10, 216, 248, 13, 197, 229, 916, 95, 934, 915, 923, 937,
			928, 936, 931, 920, 926, 0, 198, 230, 223, 201, 32, 33, 34, 35, 164, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46,
			47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 161, 65, 66, 67, 68, 69, 70, 71, 72, 73,
			74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 196, 214, 209, 220, 167, 191, 97, 98,
			99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
			121, 122, 228, 246, 241, 252, 224
		];
		const ext = { 10: 12, 20: 94, 40: 123, 41: 125, 47: 92, 60: 91, 61: 126, 62: 93, 64: 124, 101: 8364 };
		let esc = false;
		for (let i = multipart ? 7 : 0; i < len; i++) {
			const bit = i * 7,
				byte = bit >> 3,
				shift = bit & 7;
			const septet = ((data[byte] >> shift) | ((data[byte + 1] || 0) << (8 - shift))) & 127;
			if (esc) {
				if (ext[septet] === undefined) throw Error('Invalid extension');
				text += String.fromCodePoint(ext[septet]);
				esc = false;
			} else if (septet === 27) esc = true;
			else {
				if (!base[septet]) throw Error('Invalid GSM7');
				text += String.fromCodePoint(base[septet]);
			}
		}
		if (esc) throw Error('Invalid extension');
	} else if (dcs === 8) {
		if (len < (multipart ? 8 : 2) || len > 140 || (multipart ? (len - 6) % 2 : len % 2) || data.length !== len)
			throw Error('UCS2 length');
		for (let i = multipart ? 6 : 0; i < len; i += 2) text += String.fromCharCode((data[i] << 8) | data[i + 1]);
	} else throw Error('Unsupported alphabet');
	return { to, text, concat };
}

function formatSmsDate(received) {
	if (!received || !Number.isFinite(received.unixMs)) return 'Time unavailable';
	const d = new Date(received.unixMs);
	if (!Number.isFinite(d.getTime())) return 'Time unavailable';
	return d.toLocaleString('id-ID', {
		day: '2-digit',
		month: 'short',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit'
	});
}
function mergeSmsParts(rows) {
	const groups = new Map(),
		display = [];
	for (const row of rows) {
		const m = row.decoded,
			c = m?.concat;
		// Do not merge unrelated messages with same reused reference: bind
		// alphanumeric sender, total count and a 48h window of SCTS.
		if (!c || !m.received || c.total <= 1) {
			display.push(row);
			continue;
		}
		const key = [m.sender, c.ref, c.total].join('|');
		const candidates = groups.get(key) || [];
		let group = candidates.find(g => Math.abs(g.epoch - m.received.unixMs) <= 48 * 3600000 && !g.parts.has(c.part));
		if (!group) {
			group = { epoch: m.received.unixMs, parts: new Map(), total: c.total };
			candidates.push(group);
			groups.set(key, candidates);
			display.push({ group, decoded: m });
		}
		group.parts.set(c.part, row);
	}
	return display.flatMap(item => {
		if (!item.group) return [item];
		const group = item.group;
		if (group.parts.size !== group.total) {
			// Display every available segment individually, never silently
			// hide the other parts when a multipart SMS is incomplete.
			return [...group.parts]
				.sort((a, b) => a[0] - b[0])
				.map(v => ({
					...v[1],
					decoded: { ...v[1].decoded, text: v[1].decoded.text + ' (part ' + v[0] + '/' + group.total + ')' }
				}));
		}
		const ordered = [...group.parts].sort((a, b) => a[0] - b[0]).map(v => v[1]);
		return [
			{
				...ordered[0],
				decoded: {
					...ordered[0].decoded,
					text: ordered.map(r => r.decoded.text).join(''),
					concat: null,
					multipartCount: ordered.length
				},
				indices: ordered.map(r => r.index),
				segments: ordered.map(r => ({ index: r.index, pdu: r.pdu }))
			}
		];
	});
}

function decodePrivatePdu(hex) {
	if (typeof hex !== 'string' || !/^(?:[0-9A-Fa-f]{2}){4,256}$/.test(hex)) throw Error('PDU');
	const bytes = Uint8Array.from(hex.match(/../g), b => parseInt(b, 16));
	let p = 0;
	function one() {
		if (p >= bytes.length) throw Error('PDU truncated');
		return bytes[p++];
	}
	const gsmPoints = [
		64, 163, 36, 165, 232, 233, 249, 236, 242, 199, 10, 216, 248, 13, 197, 229, 916, 95, 934, 915, 923, 937, 928,
		936, 931, 920, 926, 0, 198, 230, 223, 201, 32, 33, 34, 35, 164, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
		49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 161, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76,
		77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 196, 214, 209, 220, 167, 191, 97, 98, 99, 100, 101, 102,
		103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 228, 246,
		241, 252, 224
	];
	const ext = { 10: 12, 20: 94, 40: 123, 41: 125, 47: 92, 60: 91, 61: 126, 62: 93, 64: 124, 101: 8364 };
	function unpack7(arr, count, offset = 0) {
		let s = '',
			esc = false;
		for (let i = 0; i < count; i++) {
			let bit = offset + i * 7,
				k = bit >> 3,
				shift = bit & 7;
			if (k >= arr.length || (shift > 1 && k + 1 >= arr.length)) throw Error('GSM7 truncated');
			let v = ((arr[k] >> shift) | ((arr[k + 1] || 0) << (8 - shift))) & 127;
			if (esc) {
				if (ext[v] === undefined) throw Error('GSM7 extension');
				s += String.fromCodePoint(ext[v]);
				esc = false;
			} else if (v === 27) {
				esc = true;
			} else {
				const cp = gsmPoints[v];
				if (!cp) throw Error('GSM7 invalid');
				s += String.fromCodePoint(cp);
			}
		}
		if (esc) throw Error('GSM7 dangling escape');
		return s;
	}
	const sca = one();
	if (sca > 12 || p + sca >= bytes.length) throw Error('SMSC');
	p += sca;
	const fo = one();
	if ((fo & 3) !== 0 || fo & 128) throw Error('Not SMS-DELIVER');
	const udhi = !!(fo & 64),
		digits = one(),
		toa = one();
	if (!(toa & 128) || digits < 1 || digits > 20) throw Error('Sender');
	const alpha = (toa & 112) === 80;
	// TS 23.040 alphanumeric OA length counts USEFUL SEMI-OCTETS,
	// not characters or septets. A 10-character sender uses 18 nibbles.
	const addrBytes = Math.ceil(digits / 2);
	if (p + addrBytes > bytes.length) throw Error('Sender truncated');
	let sender = '';
	if (alpha) {
		const septetCount = Math.floor((digits * 4) / 7);
		if (!septetCount || septetCount > 11) throw Error('Alpha sender length');
		sender = unpack7(bytes.slice(p, p + addrBytes), septetCount);
	} else {
		if ((toa & 112) === 16) sender = '+';
		for (let i = 0; i < digits; i++) {
			let v = i & 1 ? bytes[p + (i >> 1)] >> 4 : bytes[p + (i >> 1)] & 15;
			if (v > 9) throw Error('Sender digit');
			sender += String(v);
		}
		if (digits & 1 && bytes[p + addrBytes - 1] >> 4 !== 15) throw Error('Sender filler');
	}
	p += addrBytes;
	if (p + 10 > bytes.length) throw Error('Header truncated');
	one();
	const dcs = one();
	// 23.038 DCS: general coding, message-waiting indication and
	// 1111xxxx message classes (commonly used for operator SMS).
	let alphabet;
	if ((dcs & 192) === 0) {
		if (dcs & 32) throw Error('Compressed SMS');
		alphabet = (dcs >> 2) & 3;
	} else if ((dcs & 240) === 240) {
		alphabet = dcs & 4 ? 1 : 0;
	} else if ((dcs & 240) === 224) {
		alphabet = 2;
	} else if ((dcs & 240) === 192 || (dcs & 240) === 208) {
		alphabet = 0;
	} else {
		throw Error('Unsupported DCS');
	}
	if (alphabet === 1) throw Error('Binary SMS');
	if (alphabet !== 0 && alphabet !== 2) throw Error('Unsupported alphabet');
	// TP-Service-Centre-Time-Stamp: 7 swapped semi-octets; last holds
	// signed UTC offset in quarter-hours. Keep original network time zone.
	const scts = bytes.slice(p, p + 7);
	p += 7;
	const decodeBcd = v => {
		const lo = v & 15,
			hi = (v >> 4) & 15;
		if (lo > 9 || hi > 9) throw Error('SCTS BCD');
		return lo * 10 + hi;
	};
	let received = null;
	try {
		const yy = decodeBcd(scts[0]);
		const year = yy < 90 ? 2000 + yy : 1900 + yy;
		const month = decodeBcd(scts[1]),
			day = decodeBcd(scts[2]);
		const hour = decodeBcd(scts[3]),
			minute = decodeBcd(scts[4]),
			second = decodeBcd(scts[5]);
		const sign = scts[6] & 8 ? -1 : 1;
		const quarters = (scts[6] & 7) * 10 + (scts[6] >> 4);
		if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 || second > 59 || quarters > 79)
			throw Error('SCTS range');
		const local = Date.UTC(year, month - 1, day, hour, minute, second);
		const candidate = new Date(local);
		if (
			candidate.getUTCFullYear() !== year ||
			candidate.getUTCMonth() + 1 !== month ||
			candidate.getUTCDate() !== day
		)
			throw Error('SCTS date');
		const timezoneMinutes = sign * quarters * 15;
		received = {
			unixMs: local - timezoneMinutes * 60000,
			timezoneMinutes,
			networkTime: `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
		};
	} catch {
		/* Broken SCTS never hides otherwise valid message text. */
	}
	const udl = one(),
		data = bytes.slice(p);
	let header = 0,
		concat = null;
	if (udhi) {
		if (!data.length) throw Error('UDH');
		header = data[0] + 1;
		if (header < 3 || header > data.length) throw Error('UDH invalid');
		// Concatenation IE: 8-bit 00/03 and 16-bit 08/04.
		for (let i = 1; i < header; ) {
			if (i + 2 > header) throw Error('UDH IE');
			const ie = data[i++],
				size = data[i++];
			if (i + size > header) throw Error('UDH IE length');
			if ((ie === 0 && size === 3) || (ie === 8 && size === 4)) {
				const ref = ie === 0 ? data[i] : (data[i] << 8) | data[i + 1];
				const total = data[i + size - 2],
					part = data[i + size - 1];
				if (!total || total > 32 || part < 1 || part > total) throw Error('UDH multipart');
				concat = { ref, total, part };
			}
			i += size;
		}
	}
	let text = '';
	if (alphabet === 0) {
		if (udl > 160 || data.length !== Math.ceil((udl * 7) / 8)) throw Error('GSM7 size');
		const skip = udhi ? Math.ceil((header * 8) / 7) : 0;
		if (skip > udl) throw Error('UDH size');
		text = unpack7(data, udl - skip, skip * 7);
	} else {
		if (udl > 140 || data.length !== udl || (udl - header) & 1) throw Error('UCS2 size');
		for (let i = header; i < data.length; i += 2) {
			let cp = (data[i] << 8) | data[i + 1];
			if (cp >= 0xd800 && cp <= 0xdbff) {
				if (i + 3 >= data.length) throw Error('UCS2 surrogate');
				const low = (data[i + 2] << 8) | data[i + 3];
				if (low < 0xdc00 || low > 0xdfff) throw Error('UCS2 surrogate');
				cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
				i += 2;
			} else if (cp >= 0xdc00 && cp <= 0xdfff) throw Error('UCS2 surrogate');
			if (!cp) throw Error('NUL');
			text += String.fromCodePoint(cp);
		}
	}
	if (!sender || sender.length > 80 || text.length > 4096) throw Error('Message size');
	return { sender, text, received, concat };
}

globalThis.VeciSmsCodec = Object.freeze({
 buildSmsSubmit, buildSmsSubmitSegments, decodeSentPdu,
 decodePrivatePdu, mergeSmsParts, formatSmsDate
});
})();
