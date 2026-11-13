export function formatBytes(value = 0) {
	const bytes = Number(value) || 0;
	if (bytes < 1024) return `${bytes} B`;
	const units = ['KB', 'MB', 'GB', 'TB'];
	let size = bytes / 1024;
	let index = 0;
	while (size >= 1024 && index < units.length - 1) {
		size /= 1024;
		index += 1;
	}
	return `${size >= 100 ? size.toFixed(0) : size.toFixed(1)} ${units[index]}`;
}

export function formatDuration(seconds = 0) {
	let value = Math.max(0, Number(seconds) || 0);
	const days = Math.floor(value / 86400);
	value %= 86400;
	const hours = Math.floor(value / 3600);
	value %= 3600;
	const minutes = Math.floor(value / 60);
	if (days) return `${days}d ${hours}h`;
	if (hours) return `${hours}h ${minutes}m`;
	return `${minutes}m`;
}

export function formatMemory(memory = {}) {
	const total = Number(memory.total) || 0;
	const free = Number(memory.free) || 0;
	const buffered = Number(memory.buffered) || 0;
	const cached = Number(memory.cached) || 0;
	const available = free + buffered + cached;
	const used = Math.max(0, total - available);
	return { total, used, available, percent: total ? Math.round((used / total) * 100) : 0 };
}

export function firstAddress(iface = {}) {
	return iface['ipv4-address']?.[0]?.address || iface['ipv6-address']?.[0]?.address || '—';
}

export function humanProtocol(proto = '') {
	const labels = {
		static: 'Static',
		dhcp: 'DHCP',
		dhcpv6: 'DHCPv6',
		pppoe: 'PPPoE',
		qmi: 'QMI',
		mbim: 'MBIM',
		ncm: 'NCM',
		modemmanager: 'ModemManager',
		wireguard: 'WireGuard'
	};
	return labels[proto] || (proto ? proto.toUpperCase() : 'Unknown');
}

export function relativeExpiry(seconds = 0) {
	const value = Number(seconds) || 0;
	if (!value) return 'Permanent';
	if (value < 60) return `${value}s`;
	if (value < 3600) return `${Math.floor(value / 60)}m`;
	return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`;
}
