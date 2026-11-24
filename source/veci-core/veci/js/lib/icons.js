const paths = {
	home: '<path d="M3 11.5 12 4l9 7.5v8a1.5 1.5 0 0 1-1.5 1.5h-5v-6h-5v6h-5A1.5 1.5 0 0 1 3 19.5z"/>',
	globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
	wifi: '<path d="M4 9a12 12 0 0 1 16 0M7 12.5a7.5 7.5 0 0 1 10 0M10 16a3 3 0 0 1 4 0"/><circle cx="12" cy="19" r="1"/>',
	signal: '<path d="M5 20v-3M9.5 20v-6M14.5 20v-10M19 20V5"/>',
	devices:
		'<rect x="3" y="4" width="13" height="10" rx="2"/><path d="M8 19h9M12 14v5"/><rect x="17" y="8" width="4" height="8" rx="1"/>',
	shield: '<path d="M12 3 20 6v6c0 5-3.4 8.1-8 9-4.6-.9-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
	network:
		'<rect x="3" y="3" width="6" height="5" rx="1"/><rect x="15" y="16" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/><path d="M6 8v4h12v4M6 12v4"/>',
	system: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.8 1.8 0 0 0 .36 2l.05.05-2.76 2.76-.05-.05a1.8 1.8 0 0 0-2-.36 1.8 1.8 0 0 0-1.1 1.65V21h-3.8v-.07A1.8 1.8 0 0 0 9 19.3a1.8 1.8 0 0 0-2 .36l-.05.05-2.76-2.76.05-.05a1.8 1.8 0 0 0 .36-2A1.8 1.8 0 0 0 3 13.9H3V10h.07A1.8 1.8 0 0 0 4.7 9a1.8 1.8 0 0 0-.36-2l-.05-.05 2.76-2.76.05.05a1.8 1.8 0 0 0 2 .36A1.8 1.8 0 0 0 10.1 3H14v.07A1.8 1.8 0 0 0 15 4.7a1.8 1.8 0 0 0 2-.36l.05-.05 2.76 2.76-.05.05a1.8 1.8 0 0 0-.36 2 1.8 1.8 0 0 0 1.65 1.1H21V14h-.07A1.8 1.8 0 0 0 19.4 15z"/>',
	apps: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
	terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
	logout: '<path d="M10 5H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h5M14 8l4 4-4 4M8 12h10"/>',
	menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
	chevron: '<path d="m9 18 6-6-6-6"/>',
	refresh:
		'<path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11M5.5 15A7 7 0 0 0 18 17.5l2-4.5"/>',
	power: '<path d="M12 3v9"/><path d="M7.2 5.8a8 8 0 1 0 9.6 0"/>',
	lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>'
};

export function icon(name, className = '') {
	const body = paths[name] || paths.chevron;
	return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

export function hydrateIcons(root = document) {
	root.querySelectorAll('[data-icon]').forEach(node => {
		node.innerHTML = icon(node.dataset.icon, 'svg-icon');
	});
}
