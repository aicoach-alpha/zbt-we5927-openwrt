function renderBackup(createElement) {
  const link = (target, label) => createElement('p', [
    createElement('a', {attrs: {href: '/oem-tools/#' + target}}, label)
  ]);
  return createElement('div', {staticClass: 'form-wrap mb20'}, [
    createElement('h2', 'Cadangan konfigurasi'),
    createElement('p', 'Login ulang untuk mengakses arsip pribadi.'),
    link('backup-export', 'Unduh cadangan konfigurasi'),
    link('backup-restore-file', 'Pilih dan periksa arsip untuk restore'),
    link('reset-check', 'Periksa kesiapan reset pabrik')
  ]);
}
