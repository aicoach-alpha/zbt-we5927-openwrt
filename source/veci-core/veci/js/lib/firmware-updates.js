/* Manual/OTA firmware management via existing VeCI RPC.
 * Never flash without a signed validation token and user confirmation.
 */
export async function bindFirmwareUpdates({ api, root, toast, confirm, nativeFirmwareCheck }) {
	const find = id => root.querySelector('#' + id);
	const info = find('fw-status'),
		otaInfo = find('fw-ota-status');
	const file = find('fw-file'),
		checksum = find('fw-sha');
	const upload = find('fw-upload'),
		check = find('fw-check');
	const download = find('fw-download'),
		apply = find('fw-apply');
	let busy = false,
		ota = null,
		token = null,
		signed = false,
		limit = 7808 * 1024;
	const call = (method, args = {}, timeout = 15000) => api.veci(method, args, { timeout });
	const ok = result => {
		if (!result || result.ok !== true) throw Error(String(result?.error || 'Firmware backend unavailable'));
		return result;
	};
	const report = value => {
		info.textContent = value;
	};
	function refresh() {
		upload.disabled = busy;
		check.disabled = busy;
		download.disabled = busy || !ota;
		apply.hidden = !token || !signed;
		apply.disabled = busy || !token || !signed;
	}
	function resetApply() {
		token = null;
		signed = false;
		refresh();
	}
	function validated(response) {
		ok(response);
		if (response.validated !== true) throw Error('Image validation failed');
		signed = response.signature_verified === true;
		token = signed && /^[a-f0-9]{64}$/.test(response.apply_token || '') ? response.apply_token : null;
		report(
			signed && token
				? 'Firmware validated, signed and board-compatible. Explicit confirmation required before flashing.'
				: 'Image parsed, but publisher signature is not verified. Flashing blocked.'
		);
		refresh();
	}
	async function guarded(task) {
		if (busy) return;
		busy = true;
		refresh();
		try {
			await task();
		} catch (error) {
			report('Error: ' + String(error?.message || 'Firmware action failed').slice(0, 160));
			toast('Firmware action failed; router not flashed.', 'error');
		} finally {
			busy = false;
			refresh();
		}
	}
	try {
		const status = await call('firmwareStatus');
		if (!Number.isSafeInteger(status?.max_bytes) || status.max_bytes <= 0)
			throw Error('Firmware metadata unavailable');
		limit = status.max_bytes;
		report(
			'Board: ' + String(status.board || 'unknown') + '; maximum image ' + (limit / 1048576).toFixed(2) + ' MiB.'
		);
		otaInfo.textContent =
			status.signature_policy === 'required'
				? 'Signed updates only.'
				: 'Development profile: firmware signing is not configured; flashing blocked.';
	} catch {
		report('Firmware service is not available in this router build.');
		upload.disabled = true;
		check.disabled = true;
		download.disabled = true;
		apply.hidden = true;
		return;
	}

	upload.addEventListener('click', () =>
		guarded(async () => {
			resetApply();
			const selected = file.files?.[0],
				sha = checksum.value.trim().toLowerCase();
			if (!selected || !/\.bin$/i.test(selected.name) || selected.size < 1 || selected.size > limit)
				throw Error('Select a compatible sysupgrade .bin within router image size limit');
			if (!/^[a-f0-9]{64}$/.test(sha)) throw Error('Enter the trusted publisher SHA-256 (64 hex chars)');
			const start = ok(await call('firmwareUploadStart', { filename: selected.name, size: selected.size }));
			if (!/^[a-f0-9]{64}$/.test(start.upload_id || '')) throw Error('Invalid upload identifier');
			let sequence = 0;
			for (let offset = 0; offset < selected.size; offset += 12288) {
				const bytes = new Uint8Array(await selected.slice(offset, offset + 12288).arrayBuffer());
				const data = btoa(String.fromCharCode(...bytes));
				ok(await call('firmwareUploadChunk', { upload_id: start.upload_id, sequence, data }, 30000));
				sequence++;
				report('Upload: ' + Math.min(100, Math.round(((offset + bytes.length) * 100) / selected.size)) + '%');
			}
			const finish = ok(await call('firmwareUploadFinish', { upload_id: start.upload_id }));
			if (finish.sha256 !== sha) throw Error('Image SHA-256 does not match the publisher checksum');
			report('Checksum verified. Running router image validation.');
			validated(await call('firmwareValidate', { expected_sha256: sha }, 60000));
		})
	);

	check.addEventListener('click', () =>
		guarded(async () => {
			ota = null;
			refresh();
			// Board-native channel check fails closed on unsigned releases.
			const native =
				typeof nativeFirmwareCheck === 'function' ? await nativeFirmwareCheck().catch(() => null) : null;
			if (native?.ok === true && ['no_release', 'unverified_release'].includes(native.state)) {
				otaInfo.textContent =
					native.state === 'no_release'
						? 'No OTA firmware release has been published.'
						: 'OTA release metadata is not verified. Download and flashing blocked.';
				return;
			}
			const result = ok(await call('firmwareRemoteCheck', {}, 30000));
			if (result.available !== true) otaInfo.textContent = 'No OTA firmware release has been published.';
			else if (result.compatible !== true)
				otaInfo.textContent = 'Available release is not compatible with this board.';
			else if (result.update_available !== true) otaInfo.textContent = 'No newer firmware for this build.';
			else {
				ota = result;
				otaInfo.textContent = 'Compatible update: ' + String(result.version || 'unknown').slice(0, 60);
			}
			refresh();
		})
	);

	download.addEventListener('click', () =>
		guarded(async () => {
			if (!ota) return;
			const accepted = await confirm({
				title: 'Download and verify OTA firmware?',
				message: 'The image will be staged in router RAM, not flashed.',
				confirmLabel: 'Download image'
			});
			if (!accepted) return;
			resetApply();
			report('Downloading firmware image to RAM...');
			const result = ok(await call('firmwareRemoteDownload', {}, 120000));
			if (!/^[a-f0-9]{64}$/i.test(ota.sha256 || '') || result.sha256 !== ota.sha256)
				throw Error('OTA checksum mismatch');
			validated(await call('firmwareValidate', { expected_sha256: ota.sha256 }, 60000));
		})
	);

	apply.addEventListener('click', () =>
		guarded(async () => {
			if (!token || !signed) return;
			const accepted = await confirm({
				title: 'Flash verified firmware and reboot?',
				message:
					'Internet service will be interrupted. The router must stay powered. Current settings will be preserved.',
				confirmLabel: 'Flash and reboot',
				tone: 'danger'
			});
			if (!accepted) return;
			const once = token;
			resetApply();
			ok(await call('firmwareApply', { apply_token: once, keep_settings: true }));
			report('Firmware application accepted. Wait for the router to reboot; do not disconnect power.');
			toast('Firmware upgrade started.', 'success');
		})
	);
	refresh();
}
