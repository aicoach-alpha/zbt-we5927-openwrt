import { badge, escapeHtml, setBusy } from '/veci/js/lib/dom.js';

export default {
	async render({ api, root, toast, confirm, back, app }) {
		let status = await api.call('veci.app.guest', 'status', {});

		const draw = () => {
			root.innerHTML = `
				<div class="page-intro">
					<div>
						<p class="eyebrow">ROUTER APP</p>
						<h2>${escapeHtml(app.name || 'Guest portal')}</h2>
						<p>Create an isolated guest Wi-Fi with a captive portal managed by VeCI.</p>
					</div>
					<button id="guest-back" class="button button-secondary" type="button">Back to Apps</button>
				</div>

				<div class="content-grid content-grid-2">
					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">STATUS</p><h3>Guest network</h3></div>
							${status.enabled ? badge('Portal enabled', 'success') : status.configured ? badge('Configured', 'info') : badge('Not configured', 'neutral')}
						</div>
						<div class="detail-list">
							<div><span>Guest gateway</span><strong>${escapeHtml(status.guest_ip || '10.20.0.1')}</strong></div>
							<div><span>Radio</span><strong>${escapeHtml(status.radio || 'radio0')}</strong></div>
							<div><span>Authentication</span><strong>${status.auth_mode === 'credentials' ? 'Voucher credentials' : 'Click to continue'}</strong></div>
						</div>
						<div class="panel-actions">
							${!status.configured ? '<button id="guest-provision" class="button button-primary" type="button">Provision guest network</button>' : ''}
							${status.configured && !status.enabled ? '<button id="guest-enable" class="button button-primary" type="button">Enable portal</button>' : ''}
							${status.enabled ? '<button id="guest-disable" class="button button-danger" type="button">Disable portal</button>' : ''}
						</div>
					</article>

					<article class="panel">
						<div class="panel-heading"><div><p class="eyebrow">SETTINGS</p><h3>Guest access</h3></div></div>
						<form id="guest-form">
							<label class="field">
								<span>Guest Wi-Fi name</span>
								<input id="guest-ssid" maxlength="32" value="${escapeHtml(status.ssid || 'VeCI-Guest')}" />
							</label>
							<label class="field">
								<span>Idle timeout (seconds)</span>
								<input id="guest-idle" inputmode="numeric" value="${escapeHtml(status.idle_timeout || '600')}" />
							</label>
							<label class="field">
								<span>Session timeout (seconds, 0 = unlimited)</span>
								<input id="guest-session" inputmode="numeric" value="${escapeHtml(status.session_timeout || '3600')}" />
							</label>
							<button id="guest-save" class="button button-secondary" type="submit">Save settings</button>
						</form>
					</article>
				</div>

				<div class="notice-card">
					<strong>Guest isolation is intentional.</strong>
					<p>The VeCI guest profile uses a dedicated 10.20.0.0/24 network and firewall zone. The portal only forwards authenticated clients toward WAN and does not bridge them into LAN.</p>
				</div>
			`;

			root.querySelector('#guest-back')?.addEventListener('click', back);

			const runAction = async (id, action, label) => {
				const button = root.querySelector(id);
				if (!button) return;
				button.addEventListener('click', async () => {
					const allowed = await confirm({
						title: `${label} guest portal?`,
						message: action === 'disable'
							? 'Guest clients will lose captive portal access until it is enabled again.'
							: 'Network, firewall, DHCP and web services may reload briefly while the guest portal is applied.',
						confirmLabel: label,
						tone: action === 'disable' ? 'danger' : 'primary'
					});
					if (!allowed) return;
					setBusy(button, true, 'Applying…');
					try {
						const result = await api.call('veci.app.guest', 'action', { action }, { timeout: 60000 });
						if (!result.ok) throw new Error(result.error || 'Guest portal action failed');
						status = await api.call('veci.app.guest', 'status', {});
						draw();
						toast(`Guest portal: ${label.toLowerCase()} complete.`, 'success');
					} catch (error) {
						toast(error.message || 'Could not update guest portal.', 'error');
						setBusy(button, false);
					}
				});
			};

			runAction('#guest-provision', 'provision', 'Provision');
			runAction('#guest-enable', 'enable', 'Enable');
			runAction('#guest-disable', 'disable', 'Disable');

			root.querySelector('#guest-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#guest-save');
				setBusy(button, true, 'Saving…');
				try {
					const result = await api.call('veci.app.guest', 'save', {
						ssid: root.querySelector('#guest-ssid').value.trim(),
						idle_timeout: root.querySelector('#guest-idle').value.trim(),
						session_timeout: root.querySelector('#guest-session').value.trim()
					});
					if (!result.ok) throw new Error(result.error || 'Could not save guest settings');
					status = await api.call('veci.app.guest', 'status', {});
					draw();
					toast('Guest portal settings saved.', 'success');
				} catch (error) {
					toast(error.message || 'Could not save guest settings.', 'error');
					setBusy(button, false);
				}
			});
		};

		draw();
	}
};
