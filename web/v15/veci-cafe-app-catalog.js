/*
 * VeCI General v15 — capabilities catalog for small WE5927 café routers.
 * UI metadata, not a statement that software is installed or fits in flash.
 * Every installable capability requires an authenticated package backend,
 * exact APK feed match and dependency/flash checks before installation.
 */
export const VECI_CAFE_CATALOG = Object.freeze([
  {id:'hotspot',title:'Hotspot Portal',category:'Cafe & Voucher',priority:'P0',mode:'optional',
   package:'opennds',description:'Portal login Wi-Fi tamu. APK opennds belum ditemukan pada indeks feed resmi 25.12.5 mipsel_24kc; perlu build khusus versi firmware ini, bukan paket snapshot.',
   prerequisites:['LAN tamu terpisah dari admin','Portal/guest firewall rules','Build APK openNDS kompatibel 25.12.5 yang ditandatangani']},
  {id:'voucher-manager',title:'Voucher Manager',category:'Cafe & Voucher',priority:'P0',mode:'development',
   package:null,description:'Kode voucher dan paket durasi/kecepatan/kuota via openNDS ThemeSpec; butuh pengelola voucher dan penyimpanan aman di luar flash router.',
   prerequisites:['openNDS + ThemeSpec voucher','Penyimpanan voucher persisten di luar flash','Guest network isolation']},
  {id:'guest-wifi',title:'Guest Wi-Fi',category:'Cafe & Voucher',priority:'P0',mode:'builtin',
   route:'#/wi-fi',description:'SSID tamu terpisah dari jaringan admin; isolasi klien melalui firewall/bridge bawaan.',
   prerequisites:['Konfigurasi SSID dan zona tamu']},
  {id:'client-manager',title:'Connected Clients',category:'Cafe & Voucher',priority:'P0',mode:'builtin',
   route:'#/devices',description:'Lihat perangkat dan akses klien. Blokir/putuskan klien memerlukan izin kontrol jaringan.',
   prerequisites:[]},
  {id:'bandwidth',title:'Smart Queue (SQM)',category:'Bandwidth & QoS',priority:'P1',mode:'optional',
   package:'sqm-scripts',description:'Fairness dan pengurangan bufferbloat. Periksa CPU, qdisc, dependencies dan overlay sebelum instalasi.',
   prerequisites:['SQM kernel qdisc tersedia','Konfigurasi kecepatan WAN sesuai kondisi LTE']},
  {id:'speed-profiles',title:'Speed Profiles',category:'Bandwidth & QoS',priority:'P1',mode:'development',
   package:null,description:'Profil 2/5/10 Mbps dan pembatasan kecepatan per voucher/klien. Bukan fitur otomatis SQM.',
   prerequisites:['Hotspot atau kontrol klien','Pengaturan traffic shaping']},
  {id:'device-quota',title:'Data & Time Limits',category:'Bandwidth & QoS',priority:'P1',mode:'development',
   package:null,description:'Batas kuota MB/GB dan durasi voucher, plus tindakan ketika kuota habis.',
   prerequisites:['Voucher session accounting','Meter per klien']},
  {id:'firewall',title:'Firewall & Guest Isolation',category:'Network & Security',priority:'P0',mode:'builtin',
   route:'#/security',description:'Lindungi admin router dan isolasi jaringan tamu dari LAN privat.',
   prerequisites:[]},
  {id:'dns-filter',title:'DNS Filtering Lite',category:'Network & Security',priority:'P2',mode:'optional',
   package:'adblock-fast',description:'Filter DNS ringan dengan daftar terbatas; hindari list besar pada RAM/flash kecil.',
   prerequisites:['dnsmasq dukung konfigurasi filter']},
  {id:'ddns',title:'Dynamic DNS',category:'Network & Security',priority:'P2',mode:'optional',
   package:'ddns-scripts',description:'Perbarui hostname publik untuk akses jarak jauh; LTE bisa berada di CGNAT.',
   prerequisites:['Layanan DNS dinamis','Internet terhubung']},
  {id:'wireguard',title:'WireGuard',category:'Network & Security',priority:'P2',mode:'optional',
   package:'luci-proto-wireguard',description:'VPN administrasi jika ruang flash, kernel dan dependensi cukup; tidak wajib untuk hotspot.',
   prerequisites:['Dukungan kernel','Ruang instalasi mencukupi']},
  {id:'data-meter',title:'Data Meter',category:'Monitoring & Maintenance',priority:'P0',mode:'builtin',
   route:'/veci/data-meter.html',description:'Pemakaian trafik lokal. Bukan informasi sisa kuota operator.',
   prerequisites:[]},
  {id:'lte-watchdog',title:'Fast LTE Reconnect',category:'Monitoring & Maintenance',priority:'P0',mode:'builtin',
   route:'#/cellular',description:'Watchdog pemulihan LTE. Sudah dikonfigurasi 10 detik × 3 kegagalan.',
   prerequisites:[]},
  {id:'backup',title:'Backup & Restore',category:'Monitoring & Maintenance',priority:'P0',mode:'builtin',
   route:'#/system',description:'Ekspor dan pulihkan konfigurasi router sebelum membuat perubahan hotspot.',
   prerequisites:[]}
]);
// Homepage shows only essentials that matter to a café; optional extras remain
// in the extended catalog but do not crowd the small-router Apps dashboard.
export const VECI_CAFE_ESSENTIAL_IDS = Object.freeze([
 'hotspot','voucher-manager','guest-wifi','client-manager','bandwidth',
 'speed-profiles','device-quota','firewall','data-meter','lte-watchdog','backup'
]);
export function cafeEssentials(){
 return VECI_CAFE_CATALOG.filter(item=>VECI_CAFE_ESSENTIAL_IDS.includes(item.id));
}
export const VECI_CAFE_CATEGORIES = Object.freeze([
  'Cafe & Voucher','Bandwidth & QoS','Network & Security','Monitoring & Maintenance'
]);
export function validateCatalog(cards=VECI_CAFE_CATALOG) {
  const ids=new Set();
  for(const item of cards){
    if(!item.id || ids.has(item.id) || !/^[a-z0-9-]+$/.test(item.id)) throw new Error('duplicate_or_invalid_catalog_id');
    if(!['builtin','optional','development'].includes(item.mode)) throw new Error('invalid_catalog_mode');
    if(item.mode==='optional' && !/^[a-z0-9][a-z0-9+_.-]*$/.test(item.package||'')) throw new Error('missing_package_mapping');
    if(item.mode!=='optional' && item.package) throw new Error('nonoptional_package_disallowed');
    if(item.mode==='builtin' && (!item.route || !/^(#\/|\/veci\/)/.test(item.route))) throw new Error('builtin_route_missing');
    ids.add(item.id);
  }
  return {count:ids.size};
}
