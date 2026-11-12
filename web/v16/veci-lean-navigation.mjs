/*
 * VeCI v16: ONE canonical owner per router feature, six top-level groups.
 * Source adapter: needs the actual authenticated SPA's links and must not
 * manufacture routes or mutate the live network. No runtime dependencies.
 *
 * Feature identifiers are unique; firmware OTA belongs only to Settings.
 * Updates inside an old System page must be removed from that page's source
 * when its actual authenticated SPA code is available.
 */
export const GROUPS = Object.freeze([
  Object.freeze({ id: 'home', title: 'Home', features: ['dashboard'] }),
  Object.freeze({ id: 'internet', title: 'Internet', features: ['internet', 'cellular'] }),
  Object.freeze({ id: 'wifi', title: 'Wi-Fi', features: ['wifi'] }),
  Object.freeze({ id: 'devices', title: 'Devices', features: ['devices'] }),
  Object.freeze({ id: 'settings', title: 'Settings', features: ['network', 'security', 'system', 'ota'] }),
  Object.freeze({ id: 'apps', title: 'Apps', features: ['apps'] }),
]);
export const FEATURES = Object.freeze([
  Object.freeze({id:'dashboard', title:'Dashboard', routes:['#/home'], required:true}),
  Object.freeze({id:'internet', title:'Connection', routes:['#/internet'], required:true}),
  Object.freeze({id:'cellular', title:'Cellular / SMS', routes:['#/cellular'], required:true}),
  Object.freeze({id:'wifi', title:'Wi-Fi', routes:['#/wi-fi'], required:true}),
  Object.freeze({id:'devices', title:'Clients', routes:['#/devices'], required:true}),
  Object.freeze({id:'network', title:'Network & IPv6', routes:['#/network'], required:true}),
  Object.freeze({id:'security', title:'Security & Firewall', routes:['#/security'], required:true}),
  Object.freeze({id:'system', title:'System & Backup', routes:['#/system'], required:true}),
  // Firmware/OTA must NEVER be a second System navigation entry.
  // Source inventory decides whether its existing route is update or firmware.
  Object.freeze({id:'ota', title:'Firmware & OTA', routes:['#/update', '#/firmware'], required:false}),
  Object.freeze({id:'apps', title:'Apps', routes:['#/apps'], required:true}),
]);

function cleanHref(href) {
  return typeof href === 'string' ? href.trim().toLowerCase() : '';
}

/** Pure source-inventory planner. Never invents a missing page or route. */
export function planMenu(entries) {
  if (!Array.isArray(entries)) throw new TypeError('route_inventory_required');
  const byHref = new Map();
  for (const entry of entries) {
    const href = cleanHref(entry?.href);
    if (!href.startsWith('#/') || /[\r\n<>"'\s]/u.test(href)) continue;
    if (!byHref.has(href)) byHref.set(href, entry);
  }
  const found = new Map();
  const missing = [];
  for (const feature of FEATURES) {
    const route = feature.routes.find(x => byHref.has(x));
    if (route) found.set(feature.id, {id:feature.id, title:feature.title, href:route, source:byHref.get(route)});
    else if (feature.required) missing.push(feature.id);
  }
  if (missing.length) return {ok:false, reason:'missing_required_source_routes', missing, groups:[]};
  const groups = GROUPS.map(group => ({
    id:group.id, title:group.title,
    items:group.features.filter(id => found.has(id)).map(id => found.get(id))
  }));
  // Feature IDs and original hrefs appear exactly once in the result.
  const all = groups.flatMap(g => g.items);
  if (new Set(all.map(x => x.id)).size !== all.length ||
      new Set(all.map(x => x.href)).size !== all.length) {
    return {ok:false, reason:'duplicate_feature', missing:[], groups:[]};
  }
  return {ok:true, groups, count:all.length, hasOta:found.has('ota')};
}

/**
 * Mount only on the verified authenticated SPA. Reuse original anchors
 * (and their existing click listeners); moving them does not call the router.
 * Returning a failure does not alter DOM or existing router navigation.
 */
export function mountLeanMenu(doc) {
  const view = doc?.querySelector?.('#app-view');
  if (!view || view.classList.contains('hidden')) return {status:'not_authenticated'};
  if (view.querySelector('.veci-lean-menu')) return {status:'already_mounted'};
  const all = [...doc.querySelectorAll('a[href^="#/"]')];
  const required = all.find(a => a.getAttribute('href')?.toLowerCase() === '#/home');
  const host = required?.closest('aside,.sidebar,#sidebar,[class*="sidebar"]');
  if (!host || !doc.body?.contains(host)) return {status:'source_sidebar_unverified'};
  const anchors = all.filter(a => host.contains(a));
  const plan = planMenu(anchors.map(a => ({href:a.getAttribute('href'), node:a})));
  if (!plan.ok) return {status:plan.reason, missing:plan.missing};
  const bar = doc.createElement('nav');
  bar.className = 'veci-lean-menu';
  bar.setAttribute('aria-label', 'VeCI navigation');
  const brand = doc.createElement('strong');
  brand.className = 'veci-lean-brand';
  brand.textContent = 'VeCI';
  bar.append(brand);
  for (const group of plan.groups) {
    if (group.items.length === 1) {
      const link = group.items[0].source.node;
      link.textContent = group.title;
      bar.append(link);
    } else {
      const details = doc.createElement('details');
      details.className = 'veci-lean-group';
      const summary = doc.createElement('summary');
      summary.textContent = group.title;
      details.append(summary);
      for (const feature of group.items) {
        const link = feature.source.node;
        link.textContent = feature.title;
        details.append(link);
      }
      bar.append(details);
    }
  }
  const logout = host.querySelector('#logout-button');
  if (logout) bar.append(logout);
  view.insertBefore(bar, view.firstChild);
  host.hidden = true;
  host.style.display = 'none';
  view.classList.add('veci-lean-layout');
  return {status:'mounted', groups:plan.groups.length, features:plan.count, ota:plan.hasOta};
}
