({
  data() {
    return {version: '', catalog: 'Status katalog belum diketahui.'};
  },
  created() {
    this.$bus.emit('changeTab', 0);
    this.$req.get('/webapi?op=get_sys_version').then(result => {
      if (result && result.code === '1' && typeof result.sysversion === 'string')
        this.version = result.sysversion;
    }).catch(() => {});
    this.$req.get('/webapi?op=online_upgrade_check').then(result => {
      if (result && String(result.code) === '-6' && result.release_status === 'unverified')
        this.catalog = 'Belum ada katalog rilis OEM terverifikasi.';
    }).catch(() => {});
  },
  render(h) {
    return h('div', {staticClass: 'form-wrap mb20'}, [
      h('h2', 'Firmware OEM Updated'),
      h('p', 'Versi OpenWrt terpasang: ' + (this.version || 'belum diketahui')),
      h('p', this.catalog),
      h('a', {attrs: {href: '/oem-tools/#firmware-image'}}, 'Pilih BIN untuk verifikasi'),
      h('p', 'Pemeriksaan memerlukan login ulang. Instalasi dari halaman ini terkunci.')
    ]);
  }
})
