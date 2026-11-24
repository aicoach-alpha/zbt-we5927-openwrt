import { escapeHtml, setBusy } from '/veci/js/lib/dom.js';

export default {
	async render({ api, root, toast, back, app }) {
		const status = await api.call('veci.app.sqm', 'status', {});
		const interfaceName = status.interface || status.recommended_interface || '';

		root.innerHTML = `
			<div class="page-intro">
				<div>
					<p class="eyebrow">ROUTER APP</p>
					<h2>${escapeHtml(app.name || 'Smart Queue')}</h2>
					<p>Shape the Internet uplink to reduce latency when the connection is busy.</p>
				</div>
				<button id="app-back" class="button button-secondary" type="button">Back to Apps</button>
			</div>

			<article class="panel">
				<form id="sqm-form">
					<label class="field">
						<span>Enable Smart Queue</span>
						<input id="sqm-enabled" type="checkbox" ${status.enabled ? 'checked' : ''} />
					</label>
					<label class="field">
						<span>Uplink device</span>
						<input id="sqm-interface" value="${escapeHtml(interfaceName)}" autocomplete="off" />
					</label>
					<p class="panel-copy">Detected default-route device: ${escapeHtml(status.recommended_interface || 'unknown')}.</p>
					<div class="content-grid content-grid-2">
						<label class="field">
							<span>Download limit (kbit/s)</span>
							<input id="sqm-download" inputmode="numeric" value="${escapeHtml(status.download || '')}" />
						</label>
						<label class="field">
							<span>Upload limit (kbit/s)</span>
							<input id="sqm-upload" inputmode="numeric" value="${escapeHtml(status.upload || '')}" />
						</label>
					</div>
					<div class="content-grid content-grid-2">
						<label class="field">
							<span>Queue discipline</span>
							<select id="sqm-qdisc">
								<option value="cake" ${status.qdisc === 'cake' ? 'selected' : ''}>CAKE</option>
								<option value="fq_codel" ${status.qdisc === 'fq_codel' ? 'selected' : ''}>FQ-CoDel</option>
							</select>
						</label>
						<label class="field">
							<span>SQM profile</span>
							<select id="sqm-script">
								<option value="piece_of_cake.qos" ${status.script === 'piece_of_cake.qos' ? 'selected' : ''}>Piece of CAKE</option>
								<option value="layer_cake.qos" ${status.script === 'layer_cake.qos' ? 'selected' : ''}>Layer CAKE</option>
								<option value="simple.qos" ${status.script === 'simple.qos' ? 'selected' : ''}>Simple</option>
							</select>
						</label>
					</div>
					<button id="sqm-save" class="button button-primary" type="submit">Save Smart Queue</button>
				</form>
			</article>
		`;

		root.querySelector('#app-back')?.addEventListener('click', back);
		const form = root.querySelector('#sqm-form');
		form?.addEventListener('submit', async event => {
			event.preventDefault();
			const button = root.querySelector('#sqm-save');
			setBusy(button, true, 'Saving…');
			try {
				const result = await api.call(
					'veci.app.sqm',
					'save',
					{
						enabled: root.querySelector('#sqm-enabled').checked,
						interface: root.querySelector('#sqm-interface').value.trim(),
						download: root.querySelector('#sqm-download').value.trim(),
						upload: root.querySelector('#sqm-upload').value.trim(),
						qdisc: root.querySelector('#sqm-qdisc').value,
						script: root.querySelector('#sqm-script').value
					},
					{ timeout: 30000 }
				);
				if (!result.ok) throw new Error(result.error || 'Could not save SQM');
				toast('Smart Queue settings saved.', 'success');
			} catch (error) {
				toast(error.message || 'Could not save Smart Queue settings.', 'error');
			} finally {
				setBusy(button, false);
			}
		});
	}
};
