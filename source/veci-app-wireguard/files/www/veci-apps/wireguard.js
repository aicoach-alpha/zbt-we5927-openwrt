import { escapeHtml, setBusy } from '/veci/js/lib/dom.js';

export default {
	async render({ api, root, toast, confirm, back, app }) {
		let status = await api.call('veci.app.wireguard', 'status', {});

		const draw = () => {
			root.innerHTML = `
				<div class="page-intro">
					<div>
						<p class="eyebrow">ROUTER APP</p>
						<h2>${escapeHtml(app.name || 'WireGuard')}</h2>
						<p>Create a lightweight WireGuard interface and manage peers without exposing the router private key.</p>
					</div>
					<button id="app-back" class="button button-secondary" type="button">Back to Apps</button>
				</div>

				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">INTERFACE</p><h3>veci_wg</h3></div></div>
					<form id="wg-form">
						<label class="field"><span>Enable at boot</span><input id="wg-enabled" type="checkbox" ${status.enabled ? 'checked' : ''} /></label>
						<div class="content-grid content-grid-2">
							<label class="field"><span>Interface address</span><input id="wg-address" value="${escapeHtml(status.address || '10.7.0.1/24')}" /></label>
							<label class="field"><span>Listen port</span><input id="wg-port" inputmode="numeric" value="${escapeHtml(String(status.listen_port || 51820))}" /></label>
						</div>
						<label class="field"><span>Allow VPN peers into LAN firewall zone</span><input id="wg-lan" type="checkbox" ${status.lan_access ? 'checked' : ''} /></label>
						<div class="detail-list"><div><span>Router public key</span><strong class="mono">${escapeHtml(status.public_key || 'Generated after first save')}</strong></div></div>
						<button id="wg-save" class="button button-primary" type="submit">Save WireGuard interface</button>
					</form>
				</article>

				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">PEERS</p><h3>Configured peers</h3></div></div>
					<div class="detail-list">
						${
							status.peers?.length
								? status.peers
										.map(
											peer => `
												<div>
													<span>${escapeHtml(peer.description || peer.id)} · ${escapeHtml(peer.allowed_ip || '')}</span>
													<strong><button class="button button-secondary" data-peer-revoke="${escapeHtml(peer.id)}" type="button">Revoke</button></strong>
												</div>
											`
										)
										.join('')
								: '<div><span>No peers configured</span><strong>—</strong></div>'
						}
					</div>
				</article>

				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">ADD PEER</p><h3>New peer</h3></div></div>
					<form id="wg-peer-form">
						<label class="field"><span>Name</span><input id="wg-peer-name" maxlength="64" /></label>
						<label class="field"><span>Peer public key</span><input id="wg-peer-key" autocomplete="off" /></label>
						<label class="field"><span>Allowed IP / CIDR</span><input id="wg-peer-allowed" placeholder="10.7.0.2/32" /></label>
						<div class="content-grid content-grid-2">
							<label class="field"><span>Endpoint host (optional)</span><input id="wg-peer-endpoint" /></label>
							<label class="field"><span>Endpoint port (optional)</span><input id="wg-peer-endpoint-port" inputmode="numeric" /></label>
						</div>
						<label class="field"><span>Persistent keepalive seconds</span><input id="wg-peer-keepalive" inputmode="numeric" value="25" /></label>
						<button id="wg-peer-add" class="button button-primary" type="submit">Add peer</button>
					</form>
				</article>
			`;

			root.querySelector('#app-back')?.addEventListener('click', back);

			root.querySelector('#wg-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#wg-save');
				setBusy(button, true, 'Saving…');
				try {
					const result = await api.call(
						'veci.app.wireguard',
						'save',
						{
							enabled: root.querySelector('#wg-enabled').checked,
							address: root.querySelector('#wg-address').value.trim(),
							listen_port: Number(root.querySelector('#wg-port').value),
							lan_access: root.querySelector('#wg-lan').checked
						},
						{ timeout: 30000 }
					);
					if (!result.ok) throw new Error(result.error || 'Could not save WireGuard');
					status = await api.call('veci.app.wireguard', 'status', {});
					draw();
					toast('WireGuard interface saved.', 'success');
				} catch (error) {
					toast(error.message || 'Could not save WireGuard.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#wg-peer-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#wg-peer-add');
				setBusy(button, true, 'Adding…');
				try {
					const result = await api.call(
						'veci.app.wireguard',
						'create',
						{
							description: root.querySelector('#wg-peer-name').value.trim(),
							public_key: root.querySelector('#wg-peer-key').value.trim(),
							allowed_ip: root.querySelector('#wg-peer-allowed').value.trim(),
							endpoint_host: root.querySelector('#wg-peer-endpoint').value.trim(),
							endpoint_port: root.querySelector('#wg-peer-endpoint-port').value.trim(),
							persistent_keepalive: root.querySelector('#wg-peer-keepalive').value.trim()
						},
						{ timeout: 30000 }
					);
					if (!result.ok) throw new Error(result.error || 'Could not add WireGuard peer');
					status = await api.call('veci.app.wireguard', 'status', {});
					draw();
					toast('WireGuard peer added.', 'success');
				} catch (error) {
					toast(error.message || 'Could not add WireGuard peer.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelectorAll('[data-peer-revoke]').forEach(button => {
				button.addEventListener('click', async () => {
					const allowed = await confirm({
						title: 'Revoke this WireGuard peer?',
						message: 'The peer will lose access as soon as the network configuration reloads.',
						confirmLabel: 'Revoke peer',
						tone: 'danger'
					});
					if (!allowed) return;
					setBusy(button, true, 'Revoking…');
					try {
						const result = await api.call('veci.app.wireguard', 'revoke', {
							id: button.dataset.peerRevoke
						});
						if (!result.ok) throw new Error(result.error || 'Could not revoke peer');
						status = await api.call('veci.app.wireguard', 'status', {});
						draw();
						toast('WireGuard peer revoked.', 'success');
					} catch (error) {
						toast(error.message || 'Could not revoke WireGuard peer.', 'error');
						setBusy(button, false);
					}
				});
			});
		};

		draw();
	}
};
