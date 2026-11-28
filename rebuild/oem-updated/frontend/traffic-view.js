({
  data() { return {sample: null, busy: false, status: 'Belum ada pembacaan.'}; },
  created() { this.refresh(); },
  methods: {
    refresh() {
      if (this.busy) return;
      this.busy = true;
      this.$req.get('/webapi?op=get_days_traffic').then(x => {
        if (!x || x.code !== '1' || String(x.window_seconds) !== '86400' ||
            x.persistent !== 'false' || !['unavailable','insufficient_samples','observed_partial'].includes(x.history_state))
          throw Error('Invalid traffic snapshot');
        this.sample = x;
        this.status = x.history_state === 'observed_partial' ? 'Data interval yang teramati; bukan total penggunaan 24 jam penuh.' : 'Riwayat belum cukup atau tidak tersedia.';
      }).catch(() => { this.sample = null; this.status = 'Pembacaan tidak tersedia.'; })
        .finally(() => { this.busy = false; });
    },
    amount(key) {
      const x = this.sample;
      return x && x.history_state === 'observed_partial' && typeof x[key] === 'string' &&
        /^\d+$/.test(x[key]) ? x[key] + ' byte' : '—';
    }
  },
  render(h) {
    return h('div', {staticClass:'form-wrap mb20'}, [
      h('h2','Traffic history — 24 jam'),
      h('p','Pengukuran lokal dalam RAM, bukan kuota operator. Data hilang saat reboot.'),
      h('button',{attrs:{type:'button',disabled:this.busy},on:{click:this.refresh}},'Refresh'),
      h('p',{attrs:{role:'status'}},this.status),
      h('table',{staticClass:'table'},[
        h('thead',[h('tr',[h('th','Interface'),h('th','RX'),h('th','TX')])]),
        h('tbody',[
          h('tr',[h('td','LTE'),h('td',this.amount('lte_rx_bytes')),h('td',this.amount('lte_tx_bytes'))]),
          h('tr',[h('td','LAN'),h('td',this.amount('lan_rx_bytes')),h('td',this.amount('lan_tx_bytes'))])
        ])
      ])
    ]);
  }
})
