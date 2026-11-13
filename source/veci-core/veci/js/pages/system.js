import { bindFirmwareUpdates } from '../lib/firmware-updates.js';
import { badge, escapeHtml, setBusy } from '../lib/dom.js';
import { formatBytes, formatDuration, formatMemory } from '../lib/format.js';

export default {
	id: 'system',
	title: 'System',
	eyebrow: 'DEVICE',
	icon: 'system',

	async render({ api, state, root, toast, confirm }) {
		const [board, info, health, systemConfig] = await Promise.all([
			api.board(),
			api.systemInfo(),
			api.veci('health').catch(() => ({})),
			api.uciGet('system').catch(() => ({ values: {} }))
		]);
		const memory = formatMemory(info.memory || {});
		const model = board.model || board.board_name || 'OpenWrt Router';
		const firmware = board.release?.description || board.release?.version || 'OpenWrt';
		const systemSection = Object.entries(systemConfig.values || {}).find(
			([, value]) => value['.type'] === 'system'
		);
		const systemSectionId = systemSection?.[0] || null;
		const configuredHostname = systemSection?.[1]?.hostname || board.hostname || 'OpenWrt';
		const configuredTimezone = systemSection?.[1]?.zonename || systemSection?.[1]?.timezone || '—';

		root.innerHTML = `
			<div class="page-intro">
				<div><h2>System</h2><p>Hardware identity comes directly from OpenWrt. VeCI never substitutes a hardcoded router model.</p></div>
				<a class="button button-secondary" href="/cgi-bin/luci/admin/system/system">Advanced system settings</a>
			</div>

			<section class="device-profile">
				<div class="device-profile-mark">V</div>
				<div class="device-profile-main">
					<p class="eyebrow">HARDWARE</p>
					<h3>${escapeHtml(model)}</h3>
					<p>${escapeHtml(board.board_name || 'OpenWrt device')}</p>
				</div>
				<div class="device-profile-status">${badge('Running', 'success')}</div>
			</section>

			<article class="panel">
				<div class="panel-heading">
					<div><p class="eyebrow">ROUTER NAME</p><h3>Hostname</h3></div>
				</div>
				<form id="hostname-form" class="inline-setting-form">
					<label class="field">
						<span>Hostname</span>
						<input id="router-hostname" value="${escapeHtml(configuredHostname)}" maxlength="63" autocomplete="off" />
					</label>
					<button id="save-hostname" class="button button-primary" type="submit">Save</button>
				</form>
				<p class="panel-copy">Use letters, numbers and hyphens only. Reboot after changing the hostname so every router service picks up the new name.</p>
			</article>

			<div class="content-grid content-grid-2">
				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">SOFTWARE</p><h3>Firmware</h3></div></div>
					<div class="detail-list">
						<div><span>OpenWrt</span><strong>${escapeHtml(firmware)}</strong></div>
						<div><span>Kernel</span><strong>${escapeHtml(board.kernel || '—')}</strong></div>
						<div><span>Platform</span><strong>${escapeHtml(board.system || board.release?.target || '—')}</strong></div>
					</div>
				</article>
				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">RESOURCES</p><h3>Runtime</h3></div></div>
					<div class="detail-list">
						<div><span>Uptime</span><strong>${escapeHtml(formatDuration(info.uptime || 0))}</strong></div>
						<div><span>Memory used</span><strong>${formatBytes(memory.used)} / ${formatBytes(memory.total)}</strong></div>
						<div><span>Load</span><strong>${escapeHtml((info.load || []).map(value => (Number(value) / 65535).toFixed(2)).join(' · ') || '—')}</strong></div>
						<div><span>Storage</span><strong>${escapeHtml(health.overlay || '—')}</strong></div>
						<div><span>Timezone</span><strong>${escapeHtml(configuredTimezone)}</strong></div>
					</div>
				</article>
			</div>

			<article class="panel">
				<div class="panel-heading"><div><p class="eyebrow">FIRMWARE UPDATE</p><h3>Manual upload & OTA</h3></div></div>
				<p class="panel-copy">Only verified firmware for this exact router may be applied. Uploads are staged in RAM; no automatic flashing occurs.</p>
				<p class="panel-copy" id="fw-status" role="status">Checking firmware backend…</p>
				<label class="field"><span>OpenWrt sysupgrade image (.bin)</span><input type="file" id="fw-file" accept=".bin" /></label>
				<label class="field"><span>Publisher SHA-256 checksum</span><input type="text" id="fw-sha" autocomplete="off" maxlength="64" placeholder="64 hex characters" /></label>
				<div class="cellular-actions"><button class="button button-secondary" type="button" id="fw-upload">Upload and validate</button></div>
				<hr />
				<p class="panel-copy" id="fw-ota-status" role="status">Check the published OTA release channel.</p>
				<div class="cellular-actions">
					<button class="button button-secondary" type="button" id="fw-check">Check for OTA updates</button>
					<button class="button button-secondary" type="button" id="fw-download" disabled>Download and validate</button>
					<button class="button button-danger" type="button" id="fw-apply" hidden>Flash verified firmware</button>
				</div>
			</article>

            <article class="panel system-log-panel">
                <div class="panel-heading">
                    <div><p class="eyebrow">LOGS</p><h3>Router events</h3></div>
                    <div class="log-controls">
                        <button class="button button-compact button-secondary" data-log-source="system" type="button" aria-pressed="true">System</button>
                        <button class="button button-compact button-secondary" data-log-source="kernel" type="button" aria-pressed="false">Kernel</button>
                        <button class="button button-compact button-primary" id="refresh-logs" type="button">Load logs</button>
                    </div>
                </div>
                <pre id="system-log-output" class="system-log-output" role="log" aria-live="polite">Logs are not loaded. Select a source and click Load logs.</pre>
                <p class="panel-copy">On-demand diagnostic data: at most 150 recent lines, 240 characters per line, and 16 KB per response. No automatic polling.</p>
            </article>

			<article class="panel danger-panel">
				<div class="panel-heading">
					<div><p class="eyebrow">POWER</p><h3>Restart router</h3></div>
					<button id="reboot-router" class="button button-danger" type="button">Reboot</button>
				</div>
				<p class="panel-copy">The router will disconnect clients temporarily while OpenWrt restarts.</p>
			</article>
		`;

		const logOutput = root.querySelector('#system-log-output');
		const logButtons = [...root.querySelectorAll('[data-log-source]')];
		const refreshLogs = root.querySelector('#refresh-logs');
		let selectedLogSource = 'system';
		let logLoading = false;
		const loadLogs = async () => {
			if (logLoading) return;
			logLoading = true;
			setBusy(refreshLogs, true, 'Loading…');
			try {
				const result = await api.veci('logs', { source: selectedLogSource, limit: 100 });
				logOutput.textContent = result.output || 'No log entries returned.';
			} catch (error) {
				logOutput.textContent = 'Logs could not be loaded.';
				toast(error.message || 'Could not read router logs', 'error');
			} finally {
				logLoading = false;
				setBusy(refreshLogs, false);
			}
		};
		logButtons.forEach(button =>
			button.addEventListener('click', () => {
				selectedLogSource = button.dataset.logSource === 'kernel' ? 'kernel' : 'system';
				logButtons.forEach(choice =>
					choice.setAttribute('aria-pressed', String(choice.dataset.logSource === selectedLogSource))
				);
				logOutput.textContent = 'Source changed. Click Load logs.';
				refreshLogs.textContent = 'Load logs';
			})
		);
		refreshLogs.addEventListener('click', loadLogs);

		const nativeFirmwareCheck = () => api.call('veci.firmware', 'check', {}, { timeout: 20000 });
		void bindFirmwareUpdates({ api, root, toast, confirm, nativeFirmwareCheck });

		const hostnameForm = root.querySelector('#hostname-form');
		hostnameForm?.addEventListener('submit', async event => {
			event.preventDefault();
			const button = root.querySelector('#save-hostname');
			const hostname = root.querySelector('#router-hostname').value.trim();
			if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(hostname)) {
				toast('Hostname must be 1–63 characters using letters, numbers and hyphens.', 'error');
				return;
			}
			if (!systemSectionId) {
				toast('OpenWrt system configuration section was not found.', 'error');
				return;
			}
			setBusy(button, true, 'Saving…');
			try {
				await api.uciSet('system', systemSectionId, { hostname });
				await api.uciCommit('system');
				toast('Hostname saved. Reboot to apply it to all services.', 'success');
			} catch (error) {
				toast(error.message || 'Could not save hostname.', 'error');
			} finally {
				setBusy(button, false);
			}
		});

		const reboot = root.querySelector('#reboot-router');
		reboot.addEventListener('click', async () => {
			const allowed = await confirm({
				title: 'Reboot this router?',
				message: 'All network connections will be interrupted for a short time.',
				confirmLabel: 'Reboot router',
				tone: 'danger'
			});
			if (!allowed) return;
			setBusy(reboot, true, 'Rebooting…');
			try {
				await api.call('system', 'reboot', {});
				toast('Reboot command sent', 'success');
			} catch (error) {
				toast(error.message, 'error');
				setBusy(reboot, false);
			}
		});

		state.board = board;
		state.system = info;
	}
};
