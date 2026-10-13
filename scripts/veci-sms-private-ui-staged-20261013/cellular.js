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

			<section class="panel" aria-labelledby="cellular-sms-count-title">
				<div class="panel-heading">
					<div><p class="eyebrow">MESSAGING</p><h3 id="cellular-sms-count-title">SMS storage</h3></div>
				</div>
				<p>See how many SMS slots are used. Nothing is queried until you press the button.</p>
				<div class="detail-list">
					<div><span>Stored SMS</span><strong id="cellular-sms-count" aria-live="polite">Not checked</strong></div>
				</div>
				<div class="cellular-actions">
					<button class="button button-secondary" id="cellular-sms-count-check" type="button">Check stored SMS count</button>
				</div>
				<p>This button checks storage totals only, never SMS content or OTP. SMS Inbox listing, if separately enabled, requires explicit administrator consent in the panel below.</p>
			</section>

			<section class="panel" aria-labelledby="cellular-sms-index-title">
				<div class="panel-heading">
					<div><p class="eyebrow">MESSAGING · ADMIN ACTION</p><h3 id="cellular-sms-index-title">SMS Inbox — metadata only</h3></div>
				</div>
				<p>Show stored SMS slot numbers, status and message sizes. No sender, message text or OTP will be shown.</p>
				<p><strong>Important:</strong> Viewing this list can mark unread SMS as read. This action cannot be undone.</p>
				<label><input id="cellular-sms-index-ack" type="checkbox" /> I understand that unread SMS may become read.</label>
				<div class="cellular-actions">
					<button class="button button-secondary" id="cellular-sms-index-open" type="button" disabled>List SMS metadata once</button>
				</div>
				<div id="cellular-sms-index-output" role="status" aria-live="polite">List not requested</div>
			</section>

			<section class="panel" id="cellular-sms-private-panel" hidden aria-labelledby="cellular-sms-private-title">
                <div class="panel-heading"><div><p class="eyebrow">PRIVATE MESSAGE · ADMIN</p><h3 id="cellular-sms-private-title">Read one SMS</h3></div></div>
                <p>Select one slot from the explicitly requested Inbox metadata list. Reading may mark this message as read. Sender and message body may contain private information or one-time passwords.</p>
                <label for="cellular-sms-private-slot">SMS slot</label>
                <select id="cellular-sms-private-slot"></select>
                <label><input id="cellular-sms-private-ack" type="checkbox" /> I choose to reveal the contents of this one SMS.</label>
                <div class="cellular-actions"><button type="button" class="button button-secondary" id="cellular-sms-private-read" disabled>Read selected SMS once</button></div>
                <div id="cellular-sms-private-output" role="status" aria-live="polite">No SMS read requested.</div>
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

		// The existing v2 endpoint reads AT+CPMS? only. Never list SMS on page load.
		const smsCountButton = root.querySelector('#cellular-sms-count-check');
		smsCountButton?.addEventListener('click', async () => {
			setBusy(smsCountButton, true, 'Checking…');
			const output = root.querySelector('#cellular-sms-count');
			try {
				const result = await api.call('veci.cellular', 'messagingStorage', {}, { timeout: 4000 });
				const valid = result?.ok === true && result.state === 'queried' &&
					result.source === 'read_only_at_cpms' &&
					Number.isSafeInteger(result.used) && Number.isSafeInteger(result.total) &&
					result.used >= 0 && result.total > 0 && result.total <= 65535 &&
					result.used <= result.total && typeof result.memory === 'string' &&
					/^[A-Z]{2}$/.test(result.memory);
				if (output) output.textContent = valid
					? `${result.used} / ${result.total} (${result.memory})` : 'Unavailable';
				if (!valid) toast('SMS storage data is currently unavailable.', 'warning');
			} catch {
				if (output) output.textContent = 'Unavailable';
				toast('Unable to read SMS storage counts.', 'warning');
			} finally {
				setBusy(smsCountButton, false);
			}
		});


        // v1.4 STAGING ONLY: panel appears only after explicit metadata
        // listing. No private RPC on page mount, refresh, or timer.
        const privatePanel = root.querySelector('#cellular-sms-private-panel');
        const privateSlot = root.querySelector('#cellular-sms-private-slot');
        const privateAck = root.querySelector('#cellular-sms-private-ack');
        const privateButton = root.querySelector('#cellular-sms-private-read');
        const privateOutput = root.querySelector('#cellular-sms-private-output');
        let listedSlots = new Set();

        function updatePrivateSlots(rows) {
            listedSlots = new Set(rows.map(row => row.index));
            privateSlot.replaceChildren();
            privateAck.checked = false;
            privateButton.disabled = true;
            privateOutput.textContent = 'No SMS read requested.';
            for (const slot of listedSlots) {
                const opt = document.createElement('option');
                opt.value = String(slot);
                opt.textContent = 'Slot ' + slot;
                privateSlot.appendChild(opt);
            }
            privatePanel.hidden = listedSlots.size === 0;
        }

        privateAck?.addEventListener('change', () => {
            privateButton.disabled = !privateAck.checked || !listedSlots.has(Number(privateSlot.value));
        });

        privateButton?.addEventListener('click', async () => {
            const slot = Number(privateSlot.value);
            if (!privateAck.checked || privateButton.disabled ||
                !Number.isSafeInteger(slot) || !listedSlots.has(slot)) return;

            // One checkbox authorizes at most one foreground attempt.
            privateAck.checked = false;
            privateButton.disabled = true;
            const consent = await confirm({
                title: 'Read the contents of SMS slot ' + slot + '?',
                message: 'Sender, message text and possibly an OTP will be visible briefly on this screen. Only this selected SMS will be requested. Continue?',
                confirmLabel: 'Read this SMS once'
            });
            if (!consent || !root.isConnected || !listedSlots.has(slot)) return;

            setBusy(privateButton, true, 'Reading once…');
            privateOutput.textContent = 'Requesting single-use permission…';
            try {
                const approval = await api.call('veci.sms.private', 'armRead', {
                    slot, scope: 'single_sms_private_read',
                    consent: 'I_CONFIRM_READ_THIS_ONE_SMS'
                }, { timeout: 5000 });
                if (approval?.ok !== true ||
                    typeof approval.token !== 'string' ||
                    !/^[0-9a-f]{32}$/.test(approval.token) ||
                    approval.expires_in_seconds !== 30)
                    throw new Error('Private approval unavailable');

                // Nonce held only in this foreground function; never logged,
                // persisted to browser storage or placed in a URL.
                const result = await api.call('veci.sms.private', 'readSlot', {
                    slot, token: approval.token
                }, { timeout: 6000 });
                if (result?.ok !== true || result.index !== slot ||
                    typeof result.text !== 'string' || result.text.length > 4096 ||
                    typeof result.sender !== 'string' || result.sender.length > 80)
                    throw new Error('SMS read unavailable');

                const message = document.createElement('pre');
                message.textContent = 'Slot ' + slot + ' · sender ' + result.sender + '\n' + result.text;
                privateOutput.replaceChildren(message);
                // Private text is visible only for a short time, including
                // when the user forgets to navigate away.
                setTimeout(() => {
                    if (privateOutput.contains(message)) {
                        message.textContent = '';
                        privateOutput.textContent = 'SMS content cleared.';
                    }
                }, 30000);
            } catch {
                privateOutput.textContent = 'Private SMS read is unavailable or not enabled for this account.';
                toast('Private SMS not read.', 'warning');
            } finally {
                setBusy(privateButton, false);
                privateButton.disabled = true;
            }
        });

		// Sensitive operation: never fetch on navigation, login, status refresh,
		// timers, reconnect or storage counts. Requires TWO foreground steps.
		// The separate veci.sms RPC is write-ACL only, not veci.cellular read.
		const indexAck = root.querySelector('#cellular-sms-index-ack');
		const indexButton = root.querySelector('#cellular-sms-index-open');
		const indexOutput = root.querySelector('#cellular-sms-index-output');
		indexAck?.addEventListener('change', () => {
			if (indexButton) indexButton.disabled = !indexAck.checked;
		});
		indexButton?.addEventListener('click', async () => {
			if (!indexAck?.checked || !indexButton || !indexOutput) return;
			// The checkbox never authorizes more than a single attempt.
			indexAck.checked = false;
			indexButton.disabled = true;
			const approved = await confirm({
				title: 'List SMS metadata once?',
				message: 'This will list SMS slot numbers and sizes. The modem may mark unread SMS as read. No message content or OTP will be shown. Continue?',
				confirmLabel: 'I accept — list once'
			});
			if (!approved) return;
			setBusy(indexButton, true, 'Listing once…');
			indexOutput.textContent = 'Listing SMS metadata once…';
			try {
				const result = await api.call('veci.sms', 'listIndex', {
					scope: 'metadata_only',
					ack_unread_status: 'I_ACCEPT_UNREAD_TO_READ'
				}, { timeout: 12000 });
				const rows = result?.messages;
				const verified = result?.ok === true &&
					result.source === 'on_demand_cmgl' &&
					result.side_effect_acknowledged === true &&
					Number.isSafeInteger(result.count) &&
					result.count >= 0 && result.count <= 16 &&
					Array.isArray(rows) && rows.length === result.count &&
					rows.every(row =>
						row && Number.isSafeInteger(row.index) &&
						row.index >= 0 && row.index <= 65535 &&
						Number.isSafeInteger(row.status) && row.status >= 0 && row.status <= 4 &&
						Number.isSafeInteger(row.tpdu_octets) &&
						row.tpdu_octets > 0 && row.tpdu_octets <= 240) &&
					new Set(rows.map(row => row.index)).size === rows.length;
				if (!verified) throw new Error('Invalid metadata response');
				// DOM text only: no untrusted innerHTML and no personal SMS body.
				const fragment = document.createDocumentFragment();
				const summary = document.createElement('p');
				summary.textContent = 'Listed ' + result.count + ' SMS slot(s). Status may have changed after listing.';
				fragment.appendChild(summary);
				const list = document.createElement('ul');
				for (const row of rows) {
					const item = document.createElement('li');
					item.textContent = 'Slot ' + row.index + ' · status ' + row.status +
						' · ' + row.tpdu_octets + ' TPDU bytes';
					list.appendChild(item);
				}
				fragment.appendChild(list);
				indexOutput.replaceChildren(fragment);
                updatePrivateSlots(rows);
			} catch {
                updatePrivateSlots([]);
				indexOutput.textContent = 'Unable to list SMS. No message text was displayed. Unread flags may still have changed.';
				toast('SMS index unavailable or not enabled for this account.', 'warning');
			} finally {
				setBusy(indexButton, false);
				indexButton.disabled = true;
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
