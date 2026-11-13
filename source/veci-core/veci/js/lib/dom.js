export function escapeHtml(value) {
	return String(value ?? '')
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#039;');
}

export function qs(selector, root = document) {
	return root.querySelector(selector);
}

export function qsa(selector, root = document) {
	return [...root.querySelectorAll(selector)];
}

export function setText(selector, value, root = document) {
	const node = qs(selector, root);
	if (node) node.textContent = value ?? '';
	return node;
}

export function setBusy(button, busy, busyLabel = 'Working…') {
	if (!button) return;
	if (busy) {
		button.dataset.originalLabel = button.textContent;
		button.disabled = true;
		button.textContent = busyLabel;
	} else {
		button.disabled = false;
		if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
		delete button.dataset.originalLabel;
	}
}

export function badge(text, tone = 'neutral') {
	return `<span class="badge badge-${escapeHtml(tone)}">${escapeHtml(text)}</span>`;
}

export function emptyState(title, detail, actionHtml = '') {
	return `
		<div class="empty-state">
			<div class="empty-icon">•••</div>
			<h3>${escapeHtml(title)}</h3>
			<p>${escapeHtml(detail)}</p>
			${actionHtml}
		</div>
	`;
}

export function skeleton(lines = 4) {
	return `<div class="skeleton-stack">${Array.from({ length: lines }, (_, i) => `<span style="width:${92 - i * 9}%"></span>`).join('')}</div>`;
}
