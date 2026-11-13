import { badge, escapeHtml } from '../lib/dom.js';

const modules = {
	guest: { path: '/veci-apps/guest.js', name: 'Guest portal' },
	voucher: { path: '/veci-apps/voucher.js', name: 'Voucher' }
};

export default {
	id: 'hotspot',
	title: 'Hotspot',
	eyebrow: 'GUEST ACCESS',
	icon: 'wifi',
	async render({ api, root, toast, confirm }) {
		const [guest, voucher] = await Promise.all([
			api.call('veci.app.guest', 'status', {}).catch(() => null),
			api.call('veci.app.voucher', 'status', {}).catch(() => null)
		]);
		const guestInstalled = guest !== null;
		const voucherInstalled = voucher !== null;
		const count = Array.isArray(voucher?.vouchers) ? voucher.vouchers.length : 0;
		root.innerHTML = `
      <div class="page-intro"><div><h2>Hotspot & vouchers</h2>
      <p>Manage a dedicated guest network and time-limited credentials using the native VeCI guest and voucher apps.</p></div>
      ${badge(guest?.enabled ? 'Guest portal active' : 'Guest portal inactive', guest?.enabled ? 'success' : 'neutral')}</div>
      <div class="content-grid content-grid-2">
      <section class="panel">
        <div class="panel-heading"><div><p class="eyebrow">GUEST NETWORK</p><h3>Captive portal</h3></div>
        ${badge(guestInstalled ? 'Installed' : 'Not installed', guestInstalled ? 'success' : 'neutral')}</div>
        <div class="detail-list">
          <div><span>Network</span><strong>${escapeHtml(guest?.ssid || 'Not configured')}</strong></div>
          <div><span>Portal</span><strong>${guest?.enabled ? 'Enabled' : 'Disabled'}</strong></div>
          <div><span>Authentication</span><strong>${guest?.auth_mode === 'credentials' ? 'Voucher credentials' : 'Click to continue / unavailable'}</strong></div>
        </div>
        ${guestInstalled ? '<button class="button button-primary" type="button" data-hotspot-module="guest">Manage guest portal</button>' : '<a class="button button-secondary" href="#/apps" data-route="apps">Install Guest app</a>'}
      </section>
      <section class="panel">
        <div class="panel-heading"><div><p class="eyebrow">VOUCHERS</p><h3>Guest credentials</h3></div>
        ${badge(voucherInstalled ? 'Installed' : 'Not installed', voucherInstalled ? 'success' : 'neutral')}</div>
        <div class="detail-list">
          <div><span>Active vouchers</span><strong>${count}</strong></div>
          <div><span>Guest ready</span><strong>${voucher?.guest_ready ? 'Yes' : 'No'}</strong></div>
        </div>
        ${voucherInstalled ? '<button class="button button-primary" type="button" data-hotspot-module="voucher">Manage vouchers</button>' : '<a class="button button-secondary" href="#/apps" data-route="apps">Install Voucher app</a>'}
      </section></div>
      ${
			voucher?.batch_supported === true
				? `
      <section class="panel" aria-labelledby="voucher-batch-heading">
        <div class="panel-heading"><div><p class="eyebrow">CAFE VOUCHERS</p><h3 id="voucher-batch-heading">Generate a voucher batch</h3></div></div>
        <p class="panel-copy">Create up to 20 unique time-limited vouchers in one batch. Export the credentials to a private CSV on this laptop.</p>
        <form id="hotspot-batch-form" class="diagnostic-form">
          <label class="field"><span>Number of vouchers (1–20)</span><input name="count" type="number" min="1" max="20" value="10" required /></label>
          <label class="field"><span>Validity</span><select name="duration">
            <option value="1800">30 minutes</option><option value="3600" selected>1 hour</option>
            <option value="10800">3 hours</option><option value="86400">1 day</option>
            <option value="604800">7 days</option></select></label>
          <button type="submit" class="button button-primary" ${voucher?.guest_ready ? '' : 'disabled'}>Create vouchers and export CSV</button>
        </form>
        <p class="panel-copy">A CSV contains active usernames and passwords. Keep it private. Requires Voucher app 1-r2 or newer and an enabled guest portal.</p>
      </section>`
				: ''
		}
      ${voucherInstalled && voucher?.batch_supported !== true ? '<p class="panel-copy">Voucher batch requires the newer signed Voucher app package. Existing single-voucher management remains available.</p>' : ''}
      <div class="notice-card"><strong>Guest isolation and access control</strong>
      <p>Guest portal and vouchers use the firmware's supported uspot integration. Provisioning or enabling the guest network can reload Wi-Fi, DHCP and firewall services. Do not activate it without checking access recovery.</p></div>
    `;
		root.querySelector('#hotspot-batch-form')?.addEventListener('submit', async event => {
			event.preventDefault();
			const form = event.currentTarget;
			const count = Number(form.elements.namedItem('count')?.value);
			const duration = Number(form.elements.namedItem('duration')?.value);
			if (
				!Number.isSafeInteger(count) ||
				count < 1 ||
				count > 20 ||
				![1800, 3600, 10800, 86400, 604800].includes(duration)
			) {
				toast('Invalid voucher count or duration.', 'error');
				return;
			}
			const submit = form.querySelector('button[type="submit"]');
			submit.disabled = true;
			try {
				const result = await api.call(
					'veci.app.voucher',
					'createBatch',
					{ count, duration: String(duration) },
					{ timeout: 45000 }
				);
				if (
					result?.ok !== true ||
					!Array.isArray(result.vouchers) ||
					result.vouchers.length !== count ||
					!result.vouchers.every(code => /^[A-F0-9]{12}$/.test(code))
				) {
					throw new Error(
						result?.error ||
							'Voucher backend did not confirm every generated code. Check the installed app version and voucher status.'
					);
				}
				const csv =
					'username,password,expires_unix\n' +
					result.vouchers.map(code => `${code},${code},${Number(result.expires)}`).join('\n') +
					'\n';
				const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
				const link = document.createElement('a');
				link.href = url;
				link.download = 'veci-vouchers-' + new Date().toISOString().slice(0, 10) + '.csv';
				document.body.appendChild(link);
				link.click();
				link.remove();
				setTimeout(() => URL.revokeObjectURL(url), 5000);
				toast(`${count} vouchers generated and exported. Store the CSV securely.`, 'success');
			} catch (error) {
				toast(error.message || 'Voucher batch creation failed.', 'error');
			} finally {
				submit.disabled = false;
			}
		});
		root.querySelectorAll('[data-hotspot-module]').forEach(button => {
			button.addEventListener('click', async () => {
				const key = button.dataset.hotspotModule;
				const moduleInfo = modules[key];
				if (!moduleInfo) return;
				button.disabled = true;
				try {
					const imported = await import(moduleInfo.path);
					if (typeof imported.default?.render !== 'function') throw new Error('App module unavailable');
					root.innerHTML = '';
					await imported.default.render({
						api,
						root,
						toast,
						confirm,
						app: { name: moduleInfo.name },
						back: () => this.render({ api, root, toast, confirm })
					});
				} catch (error) {
					toast(error.message || 'Unable to open hotspot module', 'error');
					this.render({ api, root, toast, confirm });
				}
			});
		});
	}
};
