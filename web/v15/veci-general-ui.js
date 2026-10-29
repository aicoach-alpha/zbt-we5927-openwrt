/*
 * VeCI general UI v15 — source-independent integration module.
 * The caller mounts this AFTER the existing authenticated SPA enters #app-view.
 * Reuses existing navigation nodes (hash routes and event listeners intact).
 * Eliminates ONLY two cancelled quota-related Cellular panels.
 * App action callbacks are supplied by a separately authorized package backend.
 */
const LABELS = [
  ['home', 'Home'], ['internet', 'Internet'], ['wi-fi', 'Wi-Fi'],
  ['devices', 'Devices'], ['cellular', 'Cellular'],
  ['security', 'Security'], ['network', 'Network'],
  ['system', 'System'], ['apps', 'Apps']
];
const RETIRED = [
  { eyebrow: 'XL ACCOUNT', title: 'Koneksi myXL' },
  { eyebrow: 'INDONESIA · OPERATOR', title: 'Operator Data Quota' }
];
const CARDS = ['Guest portal','Smart Queue','Dynamic DNS','WireGuard','Voucher'];
const clean = value => (value || '').replace(/\s+/g,' ').trim().toLowerCase();
function activeAppView(doc) {
  const view=doc.querySelector('#app-view');
  return view && !view.classList.contains('hidden') ? view : null;
}
function routeText(anchor) {
  const hash=(anchor.getAttribute('href')||'').toLowerCase();
  const label=clean(anchor.textContent);
  return {hash,label};
}
function findOriginalLinks(doc) {
  const anchors=[...doc.querySelectorAll('a[href^="#/"]')];
  const picked=[];
  for (const [id,label] of LABELS) {
    const candidates=anchors.filter(a=>{
      const {hash,label:actual}=routeText(a);
      return hash==='#/'+id || (actual===label.toLowerCase() && hash.startsWith('#/'));
    });
    if(candidates.length!==1) return null; // fail closed, don't invent routes.
    picked.push(candidates[0]);
  }
  return picked;
}
function oldNavHost(anchor) {
  return anchor.closest('aside,.sidebar,#sidebar,[class*="sidebar"]');
}
export function mountGeneralNavigation(doc=document) {
  const view=activeAppView(doc);
  if (!view) return {status:'not_authenticated'};
  if(view.querySelector('.veci-general-topnav')) return {status:'already_mounted'};
  const links=findOriginalLinks(doc);
  if (!links) return {status:'original_routes_not_identified'};
  const host=oldNavHost(links[0]);
  if (!host || !links.every(link=>host.contains(link))) {
    return {status:'original_sidebar_not_identified'};
  }
  const oldParent=host.parentElement;
  const header=doc.createElement('header');
  header.className='veci-general-topnav';
  const brand=doc.createElement('div');
  brand.className='veci-general-brand';
  brand.textContent='VeCI';
  const nav=doc.createElement('nav');
  nav.className='veci-general-links';
  nav.setAttribute('aria-label','Router navigation');
  // Moving existing anchors preserves their event listeners and original href.
  for(const a of links) nav.appendChild(a);
  const actions=doc.createElement('div');
  actions.className='veci-general-actions';
  const expert=doc.querySelector('#expert-link');
  if(expert && host.contains(expert)) actions.appendChild(expert);
  const logout=doc.querySelector('#logout-button');
  if(logout && host.contains(logout)) actions.appendChild(logout);
  header.append(brand,nav,actions);
  view.insertBefore(header,view.firstChild);
  host.hidden=true;
  host.style.display='none';
  view.classList.add('veci-general-layout');
  // Some old shells use a fixed left-margin; override only in the active app.
  if(oldParent && oldParent!==view && oldParent.contains(view)===false) {
    oldParent.classList.add('veci-general-old-shell');
  }
  return {status:'mounted',navigationCount:links.length};
}
function candidatePanels(doc) {
  return [...doc.querySelectorAll('#app-view section,#app-view article,#app-view .card,#app-view .panel')];
}
export function retireCarrierPanels(doc=document) {
  if(!activeAppView(doc)) return 0;
  let removed=0;
  for(const panel of candidatePanels(doc)) {
    // Match heading/eyebrow texts, not wide substring matches on parent pages.
    const texts=[...panel.querySelectorAll('h1,h2,h3,h4,h5,h6,.eyebrow,.section-label,.kicker,.card-title')]
      .map(el=>clean(el.textContent));
    const all=clean(panel.textContent);
    if(RETIRED.some(item=>(
      texts.includes(clean(item.eyebrow)) &&
      (texts.includes(clean(item.title)) || all.includes(clean(item.title))) &&
      all.length<2800
    ))) {
      // Ignore ancestors containing a nested matching card; remove smallest panel.
      if([...panel.querySelectorAll('section,article,.card,.panel')].some(child=>child!==panel &&
        RETIRED.some(x=>clean(child.textContent).includes(clean(x.title))))) continue;
      panel.remove();
      removed++;
    }
  }
  return removed;
}
export function bindGeneralApps(doc=document, callbacks={}) {
  const view=activeAppView(doc);
  if(!view) return {status:'not_authenticated'};
  let count=0;
  for(const title of CARDS) {
    const headings=[...view.querySelectorAll('h2,h3,h4,h5,h6')]
      .filter(el=>clean(el.textContent)===clean(title));
    if(headings.length!==1) continue;
    const heading=headings[0];
    const card=heading.closest('article,.card,.app-card') || heading.parentElement;
    if(!card || card.querySelector('[data-veci-app-control]')) continue;
    const buttons=doc.createElement('div');
    buttons.className='veci-general-app-actions';
    buttons.dataset.veciAppControl=title;
    if (callbacks.status && callbacks.action) {
      const actionButton=doc.createElement('button');
      actionButton.type='button';
      actionButton.className='veci-general-app-button';
      actionButton.disabled=true;
      actionButton.textContent='Checking packages…';
      buttons.appendChild(actionButton);
      callbacks.status(title).then(state=>{
        if(!actionButton.isConnected)return;
        if(!state || !state.available){
          actionButton.textContent=state?.reason||'Package unavailable';
          actionButton.disabled=true;
          return;
        }
        const installed=Boolean(state.installed);
        actionButton.textContent=installed?'Uninstall':'Install';
        actionButton.disabled=false;
        actionButton.onclick=async()=>{
          const verb=installed?'uninstall':'install';
          if(!doc.defaultView.confirm(verb+' '+title+'?'))return;
          actionButton.disabled=true;
          actionButton.textContent='Processing…';
          try {
            const result=await callbacks.action(title,verb);
            actionButton.textContent=result?.accepted?'Check status':'Action unavailable';
          } catch {
            actionButton.textContent='Action failed';
          }
        };
      }).catch(()=>{ actionButton.textContent='App service unavailable'; });
    } else {
      // Safe fallback when no authorized management backend is installed.
      const label=doc.createElement('span');
      label.textContent='Package manager not connected';
      label.className='veci-general-app-pending';
      buttons.appendChild(label);
    }
    card.appendChild(buttons);
    count++;
  }
  return {status:'cards_enhanced',count};
}
export function startVeCiGeneralUI({doc=document,apps={}}={}) {
  let queued=false;
  const reconcile=()=>{
    queued=false;
    if(!activeAppView(doc))return;
    mountGeneralNavigation(doc);
    retireCarrierPanels(doc);
    bindGeneralApps(doc,apps);
  };
  const observer=new MutationObserver(()=>{
    if(queued)return;
    queued=true;
    Promise.resolve().then(reconcile);
  });
  observer.observe(doc.body,{childList:true,subtree:true});
  reconcile();
  return ()=>observer.disconnect();
}
