import {mountLeanMenu} from './veci-lean-navigation.mjs';
import {mountIPv6Settings} from './veci-ipv6-settings.mjs';

/**
 * Called by the authenticated VeCI SPA only after route inventory is verified.
 * Does not discover or invent a backend API, install packages, change service
 * state, reload Wi-Fi, or flash firmware. Explicit opt-in mount point for IPv6.
 */
export async function mountVeCiV16({doc=document, ipv6Api=null}={}) {
  const navigation = mountLeanMenu(doc);
  const ipv6Host = doc.querySelector('#app-view [data-veci-settings-ipv6]');
  let ipv6 = {status:'not_present'};
  if (navigation.status === 'mounted' || navigation.status === 'already_mounted') {
    if (ipv6Host) ipv6 = await mountIPv6Settings(ipv6Host, ipv6Api);
  }
  return {navigation,ipv6};
}
