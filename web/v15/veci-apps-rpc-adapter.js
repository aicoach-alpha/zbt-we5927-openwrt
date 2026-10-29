/*
 * VeCI v15 Apps bridge: requires the CURRENT authenticated VeCI ApiClient.
 * This bridge does not keep its own credentials or open an unauthenticated RPC.
 * Expected api.request(sessionId,object,method,params) interface.
 */
export const VECl_APP_IDS = Object.freeze({
  'Hotspot Portal':'hotspot',
  'Guest portal':'hotspot',
  'Smart Queue':'bandwidth',
  'DNS Filtering Lite':'dns-filter',
  'Dynamic DNS':'ddns',
  'WireGuard':'wireguard',
  'Voucher Manager':'voucher-manager',
  'Voucher':'voucher-manager'
});
export function makeVeCiAppService(api) {
  if(!api || typeof api.request!=='function') throw new TypeError('authenticated_api_required');
  let snapshot=null;
  let expires=0;
  async function inventory(force=false) {
    if(!api.sessionId) throw new Error('login_required');
    const now=Date.now();
    if(!force && snapshot && expires>now) return snapshot;
    const res=await api.request(api.sessionId,'veci.apps','status',{}, {timeout:8000});
    const body=res?.[1];
    if(res?.[0]!==0 || !body?.ok) throw new Error(body?.reason||'app_manager_unavailable');
    snapshot=body;
    expires=Date.now()+3000;
    return body;
  }
  async function status(title) {
    const id=VECl_APP_IDS[title];
    if(!id) return {available:false,reason:'Unknown app'};
    const data=await inventory();
    const record=data.apps?.[id];
    if(!record || record.package==='none') return {available:false,reason:'No supported package'};
    if(data.operation?.state==='running' || data.operation?.state==='queued') {
      return {available:false,reason:'Another app operation is running'};
    }
    if(record.installed) return {available:true,installed:true};
    if(!data.feedConfigured) return {available:false,reason:'Signed repository not configured'};
    if(!record.available) return {available:false,reason:'Package absent from signed feed'};
    if(Number(data.freeOverlayKiB)<8192) return {available:false,reason:'Insufficient flash space'};
    return {available:true,installed:false};
  }
  async function action(title,verb) {
    const id=VECl_APP_IDS[title];
    if(!id || id==='voucher-manager') throw new Error('unsupported_app');
    if(verb!=='install' && verb!=='uninstall') throw new TypeError('invalid_action');
    const previous=await inventory(true);
    const meta=previous.apps?.[id];
    if(!meta || meta.package==='none') throw new Error('unsupported_app');
    if(verb==='install' && (!previous.feedConfigured || !meta.available || Number(previous.freeOverlayKiB)<8192)) {
      throw new Error('package_or_flash_not_ready');
    }
    if(verb==='uninstall' && !meta.installed) throw new Error('app_not_installed');
    const res=await api.request(api.sessionId,'veci.apps','start',{app:id,action:verb},{timeout:8000});
    snapshot=null;
    expires=0;
    const result=res?.[1];
    if(res?.[0]!==0 || !result?.accepted) throw new Error(result?.reason||'app_operation_rejected');
    return {accepted:true};
  }
  return {status,action,inventory};
}
