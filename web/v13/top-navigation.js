// VeCI v13 — horizontal navigation, framework-independent.
// Integrate only after discovering actual frontend routes and auth handling.
// Does not invent router endpoints or replace the authenticated router.
export function mountVeCiTopNav({ host, entries, currentPath, onNavigate }) {
  if (!host || typeof host.replaceChildren !== 'function') {
    throw new TypeError('navigation_host_required');
  }
  if (!Array.isArray(entries) || !entries.length || entries.length > 16) {
    throw new TypeError('navigation_entries_invalid');
  }
  const candidates = [];
  const seen = new Set();
  for (const item of entries) {
    if (!item || typeof item.title !== 'string' || !item.title.trim() ||
        item.title.length > 40 || typeof item.href !== 'string' ||
        !item.href.startsWith('/') || item.href.startsWith('//') ||
        /[\r\n<>"']/u.test(item.href) || seen.has(item.href)) {
      throw new TypeError('invalid_or_duplicate_navigation_entry');
    }
    // Retired entries are excluded by caller based on the actual source menu.
    if (item.retired === true) continue;
    seen.add(item.href);
    candidates.push(item);
  }
  if (!candidates.length) throw new TypeError('no_active_navigation_entries');
  const header = document.createElement('header');
  header.className = 'veci-v13-topbar';
  const brand = document.createElement('div');
  brand.className = 'veci-v13-brand';
  brand.textContent = 'VeCI';
  const nav = document.createElement('nav');
  nav.className = 'veci-v13-topnav';
  nav.setAttribute('aria-label', 'Navigasi utama VeCI');
  for (const item of candidates) {
    const anchor = document.createElement('a');
    anchor.className = 'veci-v13-topnav-link';
    anchor.href = item.href;
    anchor.textContent = item.title.trim();
    if (item.href === currentPath) anchor.setAttribute('aria-current', 'page');
    if (typeof onNavigate === 'function') {
      anchor.addEventListener('click', event => {
        // An actual VeCI router may use SPA navigation; preserve normal
        // browser behaviour for modified clicks and external handlers.
        if (event?.defaultPrevented || event?.metaKey || event?.ctrlKey ||
            event?.shiftKey || event?.altKey || event?.button > 0) return;
        const handled = onNavigate(item.href, event);
        if (handled === true) event.preventDefault();
      });
    }
    nav.append(anchor);
  }
  header.append(brand, nav);
  host.replaceChildren(header);
  return { header, nav, visibleEntries: candidates.length };
}
