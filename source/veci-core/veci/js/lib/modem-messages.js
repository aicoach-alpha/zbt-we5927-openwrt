// Offline-only display helpers for future opt-in modem messaging UI.
// Does not issue AT commands, initiate USSD sessions, or persist SMS/OTP.
const MAX_MESSAGE_CHARS = 1024;
const MAX_MESSAGES = 50;

// Parse the *text mode* record format returned by AT+CMGL, with an exact
// expected header and no execution. Binary/PDU records are NOT supported.
export function parseSmsTextList(raw) {
	if (typeof raw !== 'string' || raw.length > 32768) return [];
	const records = [];
	let current = null;
	for (const line of raw.replaceAll('\r', '').split('\n')) {
		const head =
			/^\+CMGL:\s*(\d{1,3}),"(REC READ|REC UNREAD|STO SENT|STO UNSENT)","([^"\r\n]{0,24})",(?:"([^"\r\n]*)")?,?"([^"\r\n]{0,48})"(?:,.*)?$/.exec(
				line
			);
		if (head) {
			if (current) records.push(current);
			current = {
				index: Number(head[1]),
				status: head[2],
				// Sanitized source in memory only; no console, cache or telemetry.
				address: head[3],
				timestamp: head[5],
				text: ''
			};
			if (records.length >= MAX_MESSAGES) break;
			continue;
		}
		if (current && line !== 'OK' && line !== 'ERROR' && !line.startsWith('+CMS ERROR:')) {
			if (current.text.length + line.length + 1 > MAX_MESSAGE_CHARS) {
				current = null; // Never show truncated OTP/message as complete.
				continue;
			}
			current.text += (current.text ? '\n' : '') + line;
		}
	}
	if (current && records.length < MAX_MESSAGES) records.push(current);
	return records.filter(item => item.index <= 255 && item.text.length > 0);
}

// AT+CUSD unsolicited output may use encoded GSM/hex payloads. Decode only
// UCS2/UTF16BE DCS=72 (0x48), otherwise return explicitly unsupported.
// A read-only parser never sends AT+CUSD or responds to interactive menus.
export function decodeUssdUcs2(payload, dcs) {
	if (dcs !== 72 || typeof payload !== 'string' || payload.length > 2048) return null;
	if (!/^(?:[0-9A-Fa-f]{4})+$/.test(payload)) return null;
	let text = '';
	for (let i = 0; i < payload.length; i += 4) {
		const unit = Number.parseInt(payload.slice(i, i + 4), 16);
		if (unit >= 0xd800 && unit <= 0xdfff) return null;
		text += String.fromCharCode(unit);
	}
	return text;
}
