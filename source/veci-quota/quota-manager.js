/* VeCI operator quota adapter manager: no operator secrets, no network I/O by default. */
(function(root, factory) {
  const api = factory(typeof module === 'object' && module.exports
    ? require('./quota-state.js') : root.VeCIQuotaState);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VeCIQuotaManager = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function(stateApi) {
  'use strict';
  const supported = new Set(['xl', 'axis', 'telkomsel', 'indosat', 'tri', 'byu', 'smartfren']);
  const errors = new Set(['not_supported', 'authentication_required', 'pending_otp', 'rate_limited', 'stale', 'unavailable']);
  function make(adapterMap, clock) {
    const adapters = Object.create(null);
    for (const [name, adapter] of Object.entries(adapterMap || {})) {
      if (!supported.has(name)) throw new Error('unsupported operator');
      if (!adapter || typeof adapter.capabilities !== 'function' || typeof adapter.quota !== 'function')
        throw new Error('invalid operator adapter');
      adapters[name] = adapter;
    }
    const now = typeof clock === 'function' ? clock : Date.now;
    function get(name) { return Object.prototype.hasOwnProperty.call(adapters, name) ? adapters[name] : null; }
    function fail(name, status) { return {operator:name, state:status, buckets:[]}; }
    async function capabilities(name) {
      const adapter = get(name);
      if (!adapter) return {operator:name,state:'not_supported',authentication:[]};
      try {
        const result = await adapter.capabilities();
        return {operator:name,state:result && result.state === 'available' ? 'available' : 'unavailable',
          authentication:Array.isArray(result && result.authentication)
            ? result.authentication.filter(x=>['otp','oauth','external'].includes(x)) : []};
      } catch (_) { return {operator:name,state:'unavailable',authentication:[]}; }
    }
    async function quota(name) {
      const adapter = get(name);
      if (!adapter) return fail(name,'not_supported');
      try {
        const value = await adapter.quota();
        return stateApi.normalize({...value,operator:name},now());
      } catch (error) {
        const code = error && error.code;
        return fail(name,errors.has(code) ? code : 'unavailable');
      }
    }
    async function act(name, method, payload) {
      const adapter = get(name);
      if (!adapter) return fail(name,'not_supported');
      if (!['start_auth','complete_auth','refresh_auth','logout'].includes(method) ||
          typeof adapter[method] !== 'function') return fail(name,'not_supported');
      try {
        const value = await adapter[method](payload);
        return {operator:name,state:value && errors.has(value.state) ? value.state :
          value && value.state === 'ok' ? 'ok' : 'unavailable'};
      } catch (error) { return fail(name,errors.has(error && error.code) ? error.code : 'unavailable'); }
    }
    return {capabilities,quota,startAuth:(n,p)=>act(n,'start_auth',p),
      completeAuth:(n,p)=>act(n,'complete_auth',p),refreshAuth:n=>act(n,'refresh_auth'),
      logout:n=>act(n,'logout')};
  }
  return {make};
});
