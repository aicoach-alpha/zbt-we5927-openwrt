import { badge, escapeHtml, setBusy } from '/veci/js/lib/dom.js';

function randomCode() {
	const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
	const bytes = new Uint8Array(8);
	crypto.getRandomValues(bytes);
	return Array.from(bytes, value => alphabet[value % alphabet.length]).join('');
}

function formatRemaining(seconds) {
	const value = Number(seconds) || 0;
	if (value < 60) return '< 1 min';
	if (value < 3600) return `${Math.ceil(value / 60)} min`;
	if (value < 86400) return `${Math.ceil(value / 3600)} h`;
	return `${Math.ceil(value / 86400)} d`;
}

export default {
	async render({ api, root, toast, confirm, back, app }) {
		let status = await api.call('veci.app.voucher', 'status', {});

		const draw = () => {
			const vouchers = Array.isArray(status.vouchers) ? status.vouchers : [];
			root.innerHTML = `
				<div class="page-intro">
					<div>
						<p class="eyebrow">ROUTER APP</p>
						<h2>${escapeHtml(app.name || 'Voucher')}</h2>
						<p>Create temporary credentials for the VeCI guest portal.</p>
					</div>
					<button id="voucher-back" class="button button-secondary" type="button">Back to Apps</button>
				</div>

				<div class="content-grid content-grid-2">
					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">CREATE</p><h3>New voucher</h3></div>
							${status.guest_ready ? badge('Guest portal ready', 'success') : badge('Enable Guest portal first', 'warning')}
						</div>
						<form id="voucher-form">
							<label class="field">
								<span>Voucher code</span>
								<div class="inline-setting-form">
									<input id="voucher-code" value="${randomCode()}" maxlength="20" autocomplete="off" />
									<button id="voucher-random" class="button button-secondary" type="button">Random</button>
								</div>
							</label>
							<label class="field">
								<span>Validity</span>
								<select id="voucher-duration">
									<option value="1800">30 minutes</option>
									<option value="3600" selected>1 hour</option>
									<option value="10800">3 hours</option>
									<option value="43200">12 hours</option>
									<option value="86400">1 day</option>
									<option value="604800">7 days</option>
								</select>
							</label>
							<button id="voucher-create" class="button button-primary" type="submit" ${status.guest_ready ? '' : 'disabled'}>Create voucher</button>
						</form>
					</article>

					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">ACTIVE</p><h3>Current vouchers</h3></div>
							${badge(String(vouchers.length), vouchers.length ? 'info' : 'neutral')}
						</div>
						<div class="detail-list">
							${vouchers.length
								? vouchers.map(v => `
									<div>
										<span><strong>${escapeHtml(v.code)}</strong><br><small>${escapeHtml(formatRemaining(v.remaining))} remaining</small></span>
										<button class="button button-secondary" data-revoke="${escapeHtml(v.code)}" type="button">Revoke</button>
									</div>
								`).join('')
								: '<div><span>No active vouchers</span><strong>—</strong></div>'}
						</div>
					</article>
				</div>

				<div class="notice-card">
					<strong>Voucher mode uses local credentials.</strong>
					<p>The voucher code is used as both username and password by the local guest portal. Expired vouchers are removed automatically by a lightweight cleaner service.</p>
				</div>
			`;

			root.querySelector('#voucher-back')?.addEventListener('click', back);
			root.querySelector('#voucher-random')?.addEventListener('click', () => {
				root.querySelector('#voucher-code').value = randomCode();
			});

			root.querySelector('#voucher-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#voucher-create');
				setBusy(button, true, 'Creating…');
				try {
					const result = await api.call('veci.app.voucher', 'create', {
						code: root.querySelector('#voucher-code').value.trim(),
						duration: root.querySelector('#voucher-duration').value
					});
					if (!result.ok) throw new Error(result.error || 'Could not create voucher');
					status = await api.call('veci.app.voucher', 'status', {});
					draw();
					toast(`Voucher ${result.code} created.`, 'success');
				} catch (error) {
					toast(error.message || 'Could not create voucher.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelectorAll('[data-revoke]').forEach(button => {
				button.addEventListener('click', async () => {
					const code = button.dataset.revoke;
					const allowed = await confirm({
						title: `Revoke voucher ${code}?`,
						message: 'This credential will stop working for new guest authentication.',
						confirmLabel: 'Revoke voucher',
						tone: 'danger'
					});
					if (!allowed) return;
					setBusy(button, true, 'Revoking…');
					try {
						const result = await api.call('veci.app.voucher', 'revoke', { code });
						if (!result.ok) throw new Error(result.error || 'Could not revoke voucher');
						status = await api.call('veci.app.voucher', 'status', {});
						draw();
						toast('Voucher revoked.', 'success');
					} catch (error) {
						toast(error.message || 'Could not revoke voucher.', 'error');
						setBusy(button, false);
					}
				});
			});
		};

		draw();
	}
};
