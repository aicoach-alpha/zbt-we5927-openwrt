import { badge, escapeHtml, setBusy } from '../lib/dom.js';

const UPLOAD_CHUNK_BYTES = 32 * 1024;

function repoBadge(channel) {
	switch (channel) {
		case 'release':
			return badge('Stable release feeds', 'success');
		case 'snapshot':
			return badge('Snapshot feed detected', 'warning');
		case 'mixed':
			return badge('Mixed feeds', 'warning');
		default:
			return badge('Repository unknown', 'neutral');
	}
}

function boolText(value) {
	return value ? 'Available' : 'Not installed';
}

function formatBytes(value) {
	const bytes = Number(value) || 0;
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
	return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
}

function chunkToBase64(buffer) {
	const bytes = new Uint8Array(buffer);
	let binary = '';
	for (let offset = 0; offset < bytes.length; offset += 8192) {
		binary += String.fromCharCode(...bytes.subarray(offset, Math.min(offset + 8192, bytes.length)));
	}
	return btoa(binary);
}

export default {
	id: 'updates',
	title: 'Updates',
	eyebrow: 'MAINTENANCE',
	icon: 'refresh',

	async render({ api, root, toast, confirm }) {
		let validationToken = '';
		let remote = null;

		const loadStatus = async () => {
			const [packageStatus, firmwareStatus] = await Promise.all([
				api.veci('updateStatus', {}, { timeout: 10000 }).catch(() => ({})),
				api.veci('firmwareStatus', {}, { timeout: 10000 }).catch(() => ({}))
			]);
			return { packageStatus, firmwareStatus };
		};

		let state = await loadStatus();

		const validateStaged = async expectedSha => {
			const result = await api.veci(
				'firmwareValidate',
				{ expected_sha256: expectedSha || '' },
				{ timeout: 60000 }
			);
			if (!result.ok || !result.validated) throw new Error(result.error || 'Firmware validation failed');
			validationToken = result.apply_token || '';
			state = await loadStatus();
			draw();
			toast('Firmware passed checksum and sysupgrade compatibility checks.', 'success');
		};

		const draw = () => {
			const status = state.packageStatus || {};
			const firmware = state.firmwareStatus || {};
			const packageUpdates = Number(status.package_updates) || 0;
			const sensitiveUpdates = Number(status.sensitive_updates) || 0;
			const optionalUpdates = Math.max(0, packageUpdates - sensitiveUpdates);
			const channel = status.repository_channel || 'unknown';
			const snapshotWarning = channel === 'snapshot' || channel === 'mixed';
			const kernelFeedMismatch = Boolean(status.kernel_feed_mismatch);
			const customFeed = Boolean(status.custom_feed_configured);
			const staged = Boolean(firmware.staged);
			const serverValidated = Boolean(firmware.validated);
			const installUnlocked = serverValidated && Boolean(validationToken);
			const maxBytes = Number(firmware.max_bytes) || 0;
			const automaticInstallSupported = Boolean(firmware.automatic_install_supported);

			root.innerHTML = `
				<div class="page-intro">
					<div>
						<h2>Router updates</h2>
						<p>Firmware images are staged in RAM, checked for this board, and must pass <code>sysupgrade -T</code> before installation is unlocked.</p>
					</div>
					<button id="refresh-update-status" class="button button-secondary" type="button">Refresh status</button>
				</div>

				<div class="content-grid content-grid-2">
					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">RUNNING FIRMWARE</p><h3>Installed image</h3></div>
							${badge('Running', 'success')}
						</div>
						<div class="detail-list">
							<div><span>OpenWrt</span><strong>${escapeHtml(status.release || '—')}</strong></div>
							<div><span>Revision</span><strong>${escapeHtml(status.revision || '—')}</strong></div>
							<div><span>Board</span><strong>${escapeHtml(firmware.board || '—')}</strong></div>
							<div><span>Build ID</span><strong>${escapeHtml(firmware.build_id ? firmware.build_id.slice(0, 12) : '—')}</strong></div>
						</div>
					</article>

					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">STAGED IMAGE</p><h3>Validation</h3></div>
							${serverValidated ? badge('Validated', 'success') : staged ? badge('Needs validation', 'warning') : badge('Empty', 'neutral')}
						</div>
						<div class="detail-list">
							<div><span>Staged</span><strong>${staged ? formatBytes(firmware.bytes) : '—'}</strong></div>
							<div><span>SHA256</span><strong>${escapeHtml(firmware.sha256 ? firmware.sha256.slice(0, 16) + '…' : '—')}</strong></div>
							<div><span>Signature policy</span><strong>${escapeHtml(firmware.signature_policy || 'development')}</strong></div>
							<div><span>Trusted signature</span><strong>${firmware.signature_verified ? 'Verified' : firmware.signature_policy === 'required' ? 'Not verified' : 'Development image'}</strong></div>
							<div><span>Image budget</span><strong>${maxBytes ? formatBytes(maxBytes) : '—'}</strong></div>
						</div>
						${staged && !installUnlocked ? `<button id="validate-staged" class="button button-secondary" type="button">${serverValidated ? 'Revalidate for install' : 'Validate staged image'}</button>` : ''}
					</article>
				</div>

				<article class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">MANUAL UPDATE</p><h3>Upload sysupgrade image</h3></div>
						${badge('Native VeCI', 'info')}
					</div>
					<p class="panel-copy">Choose a <code>.bin</code> sysupgrade image. VeCI uploads it in small chunks to avoid loading the whole file into router memory at once.</p>
					<div class="content-grid content-grid-2">
						<label class="field">
							<span>Firmware image</span>
							<input id="firmware-file" type="file" accept=".bin,application/octet-stream" />
						</label>
						<label class="field">
							<span>Expected SHA256 (optional)</span>
							<input id="firmware-sha" maxlength="64" autocomplete="off" placeholder="64 hex characters" />
						</label>
					</div>
					<div class="panel-actions">
						<button id="upload-firmware" class="button button-primary" type="button">Upload & validate</button>
						<span id="upload-progress" class="muted"></span>
					</div>
				</article>

				<article class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">GITHUB CHANNEL</p><h3>Remote firmware</h3></div>
						${firmware.manifest_url ? badge('Configured', 'success') : badge('Not configured', 'neutral')}
					</div>
					<div class="detail-list">
						<div><span>Manifest</span><strong>${escapeHtml(firmware.manifest_url || 'Firmware profile has not configured a channel')}</strong></div>
						${
							remote
								? `
							<div><span>Published release</span><strong>${remote.available === false ? 'None yet' : escapeHtml(remote.version || '—')}</strong></div>
							<div><span>Channel</span><strong>${escapeHtml(remote.channel || '—')}</strong></div>
							<div><span>Compatibility</span><strong>${remote.compatible ? 'Compatible' : 'Not compatible with this board'}</strong></div>
							<div><span>Size</span><strong>${formatBytes(remote.size)}</strong></div>
							<div><span>SHA256</span><strong>${escapeHtml(remote.sha256 ? remote.sha256.slice(0, 16) + '…' : '—')}</strong></div>
						`
								: ''
						}
					</div>
					<div class="panel-actions">
						<button id="check-remote" class="button button-secondary" type="button" ${firmware.manifest_url ? '' : 'disabled'}>Check GitHub</button>
						${remote?.compatible && remote?.update_available ? '<button id="download-remote" class="button button-primary" type="button">Download & validate</button>' : ''}
					</div>
				</article>

				<article class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">AUTOMATION</p><h3>Update policy</h3></div>
						${badge('Safe defaults', 'neutral')}
					</div>
					<form id="update-policy-form">
						<label class="field">
							<span><input id="auto-check" type="checkbox" ${firmware.auto_check ? 'checked' : ''} /> Automatically check configured firmware channel</span>
						</label>
						<label class="field">
							<span><input id="auto-download" type="checkbox" ${firmware.auto_download ? 'checked' : ''} /> Automatically download compatible firmware</span>
						</label>
						<label class="field">
							<span><input id="auto-install" type="checkbox" ${firmware.auto_install ? 'checked' : ''} ${automaticInstallSupported ? '' : 'disabled'} /> Automatically install trusted firmware after validation</span>
						</label>
						<div class="detail-list">
							<div><span>Check interval</span><strong>${Math.round((Number(firmware.check_interval) || 21600) / 3600)} h</strong></div>
							<div><span>Last automatic state</span><strong>${escapeHtml(firmware.auto_state || 'not_run')}</strong></div>
							<div><span>Last result</span><strong>${escapeHtml(firmware.auto_detail || '—')}</strong></div>
						</div>
						<p class="panel-copy">${automaticInstallSupported ? 'Automatic install is opt-in and only runs after the image passes board, checksum, sysupgrade and trusted-signature verification. It reboots the router when a verified update is found.' : 'Automatic install is locked on development firmware until a trusted VeCI firmware signing key is embedded. Automatic download may still stage and validate an image.'} VeCI never performs a blind <code>apk upgrade</code>.</p>
						<button id="save-update-policy" class="button button-secondary" type="submit">Save policy</button>
					</form>
				</article>

				<div class="content-grid content-grid-2">
					<article class="panel">
						<div class="panel-heading">
							<div><p class="eyebrow">PACKAGE INDEX</p><h3>Available package changes</h3></div>
							${repoBadge(channel)}
						</div>
						<div class="detail-list">
							<div><span>Upgradeable packages</span><strong>${packageUpdates}</strong></div>
							<div><span>Base-sensitive packages</span><strong>${sensitiveUpdates}</strong></div>
							<div><span>Other packages</span><strong>${optionalUpdates}</strong></div>
							<div><span>Kernel feed match</span><strong>${kernelFeedMismatch ? 'Mismatch — firmware rebuild required' : 'No mismatch detected'}</strong></div>
							<div><span>VeCI custom feed</span><strong>${customFeed ? 'Configured' : 'Not configured'}</strong></div>
							<div><span>owut</span><strong>${boolText(Boolean(status.owut_available))}</strong></div>
						</div>
					</article>

					<article class="panel danger-panel">
						<div class="panel-heading">
							<div><p class="eyebrow">INSTALL</p><h3>Apply validated firmware</h3></div>
							${installUnlocked ? badge('Ready', 'warning') : serverValidated ? badge('Revalidate required', 'warning') : badge('Locked', 'neutral')}
						</div>
						<p class="panel-copy">Installing firmware interrupts the network and reboots the router. This action is available only after the exact staged file passes validation.</p>
						<label class="field">
							<span><input id="keep-settings" type="checkbox" checked /> Keep current OpenWrt settings</span>
						</label>
						<button id="apply-firmware" class="button button-danger" type="button" ${installUnlocked ? '' : 'disabled'}>Install & reboot</button>
					</article>
				</div>

				<div class="notice-card">
					<strong>${
						kernelFeedMismatch
							? 'Kernel package feed does not match this custom firmware.'
							: snapshotWarning
								? 'Repository warning: development feed detected.'
								: 'Firmware images and package updates are intentionally separate.'
					}</strong>
					<p>${
						kernelFeedMismatch
							? 'Do not install offered kernel modules from a different ABI. Use the VeCI matched app feed or a tested firmware image.'
							: snapshotWarning
								? 'Do not mass-upgrade packages from mixed development feeds. Use a tested firmware image instead.'
								: 'Core libraries, kernel packages and network services move together inside a tested firmware image.'
					}</p>
				</div>
			`;

			root.querySelector('#refresh-update-status')?.addEventListener('click', async event => {
				const button = event.currentTarget;
				setBusy(button, true, 'Refreshing…');
				try {
					state = await loadStatus();
					draw();
					toast('Update status refreshed.', 'success');
				} catch (error) {
					toast(error.message || 'Could not refresh update status.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#validate-staged')?.addEventListener('click', async event => {
				const button = event.currentTarget;
				setBusy(button, true, 'Validating…');
				try {
					await validateStaged('');
				} catch (error) {
					toast(error.message || 'Firmware validation failed.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#upload-firmware')?.addEventListener('click', async event => {
				const button = event.currentTarget;
				const file = root.querySelector('#firmware-file')?.files?.[0];
				const shaInput = root.querySelector('#firmware-sha')?.value.trim().toLowerCase() || '';
				const progress = root.querySelector('#upload-progress');
				if (!file) {
					toast('Choose a firmware .bin file first.', 'error');
					return;
				}
				if (shaInput && !/^[a-f0-9]{64}$/.test(shaInput)) {
					toast('Expected SHA256 must contain exactly 64 hexadecimal characters.', 'error');
					return;
				}
				if (maxBytes && file.size > maxBytes) {
					toast(`Firmware is too large. Maximum is ${formatBytes(maxBytes)}.`, 'error');
					return;
				}

				setBusy(button, true, 'Uploading…');
				validationToken = '';
				try {
					const start = await api.veci('firmwareUploadStart', { filename: file.name, size: file.size });
					if (!start.ok || !start.upload_id)
						throw new Error(start.error || 'Could not start firmware upload');
					let sequence = 0;
					for (let offset = 0; offset < file.size; offset += UPLOAD_CHUNK_BYTES) {
						const buffer = await file
							.slice(offset, Math.min(offset + UPLOAD_CHUNK_BYTES, file.size))
							.arrayBuffer();
						const result = await api.veci(
							'firmwareUploadChunk',
							{ upload_id: start.upload_id, sequence, data: chunkToBase64(buffer) },
							{ timeout: 20000 }
						);
						if (!result.ok) throw new Error(result.error || 'Firmware upload failed');
						sequence += 1;
						if (progress)
							progress.textContent = `${Math.min(100, Math.round((result.bytes / file.size) * 100))}%`;
					}
					const finish = await api.veci(
						'firmwareUploadFinish',
						{ upload_id: start.upload_id },
						{ timeout: 20000 }
					);
					if (!finish.ok) throw new Error(finish.error || 'Could not finalize firmware upload');
					await validateStaged(shaInput);
				} catch (error) {
					toast(error.message || 'Firmware upload failed.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#check-remote')?.addEventListener('click', async event => {
				const button = event.currentTarget;
				setBusy(button, true, 'Checking…');
				try {
					const result = await api.veci('firmwareRemoteCheck', {}, { timeout: 30000 });
					if (!result.ok) throw new Error(result.error || 'Could not read remote firmware manifest');
					remote = result;
					draw();
					toast(
						result.available === false
							? 'No firmware has been published on this channel yet.'
							: result.compatible
								? result.update_available
									? 'Compatible firmware is available.'
									: 'Router already matches the remote build.'
								: 'Remote firmware does not match this board.',
						result.available === false ? 'info' : result.compatible ? 'success' : 'warning'
					);
				} catch (error) {
					toast(error.message || 'Remote update check failed.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#download-remote')?.addEventListener('click', async event => {
				const button = event.currentTarget;
				setBusy(button, true, 'Downloading…');
				validationToken = '';
				try {
					const result = await api.veci('firmwareRemoteDownload', {}, { timeout: 180000 });
					if (!result.ok) throw new Error(result.error || 'Firmware download failed');
					await validateStaged(remote?.sha256 || result.sha256 || '');
				} catch (error) {
					toast(error.message || 'Remote firmware download failed.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#update-policy-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#save-update-policy');
				setBusy(button, true, 'Saving…');
				try {
					const wantsAutoInstall = root.querySelector('#auto-install').checked;
					if (wantsAutoInstall && !firmware.auto_install) {
						const allowed = await confirm({
							title: 'Enable automatic firmware install?',
							message:
								'When a compatible firmware update is found, VeCI will download it, verify the trusted image signature and sysupgrade compatibility, then install it automatically and reboot the router.',
							confirmLabel: 'Enable automatic install',
							tone: 'danger'
						});
						if (!allowed) {
							setBusy(button, false);
							return;
						}
					}
					const result = await api.veci('firmwarePolicySave', {
						auto_check: root.querySelector('#auto-check').checked,
						auto_download: root.querySelector('#auto-download').checked,
						auto_install: wantsAutoInstall
					});
					if (!result.ok) throw new Error(result.error || 'Could not save update policy');
					state = await loadStatus();
					draw();
					toast('Firmware update policy saved.', 'success');
				} catch (error) {
					toast(error.message || 'Could not save update policy.', 'error');
					setBusy(button, false);
				}
			});

			root.querySelector('#apply-firmware')?.addEventListener('click', async () => {
				if (!validationToken) {
					toast('Validate the exact staged image again before installation.', 'error');
					return;
				}
				const keepSettings = root.querySelector('#keep-settings').checked;
				const allowed = await confirm({
					title: 'Install validated firmware?',
					message: keepSettings
						? 'The router will install the validated image, preserve configuration, and reboot. Network access will be interrupted.'
						: 'The router will install the validated image WITHOUT preserving settings and reboot. This resets configuration.',
					confirmLabel: 'Install firmware',
					tone: 'danger'
				});
				if (!allowed) return;
				const button = root.querySelector('#apply-firmware');
				setBusy(button, true, 'Starting upgrade…');
				try {
					const result = await api.veci(
						'firmwareApply',
						{ apply_token: validationToken, keep_settings: keepSettings },
						{ timeout: 10000 }
					);
					if (!result.ok) throw new Error(result.error || 'Firmware install could not start');
					validationToken = '';
					toast('Firmware installation started. The router will reboot.', 'success');
				} catch (error) {
					toast(error.message || 'Firmware installation could not start.', 'error');
					setBusy(button, false);
				}
			});
		};

		draw();
	}
};
