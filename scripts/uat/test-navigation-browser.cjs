// Serve the packaged frontend entirely from disk and exercise its actual click handlers.
const {chromium} = require('playwright');
const path = require('node:path');
const assert = require('node:assert/strict');
const ui = path.resolve(__dirname, '../../rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2');

(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROME_BIN});
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(5000);
    const errors = [];
    const calls = [];
    page.on('pageerror', error => errors.push(error.stack));
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      assert.equal(url.origin, 'https://router.test');
      if (url.pathname === '/ubus') {
        const [, object, method] = route.request().postDataJSON().params;
        calls.push([object, method]);
        let data = {};
        if (method === 'login') data = {ubus_rpc_session: '1'.repeat(32)};
        if (object === 'veci.v2.time') data = {ok:true, revision:'test', servers:'office.example', zone:'UTC', clock:'UTC'};
        return route.fulfill({json:{jsonrpc:'2.0', id:1, result:[0,data]}});
      }
      assert.ok(url.pathname.startsWith('/veci2/'));
      return route.fulfill({path:path.join(ui, path.basename(url.pathname) === 'veci2' ? 'index.html' : path.basename(url.pathname))});
    });
    await page.goto('https://router.test/veci2/');
    const login = async () => {
      await page.locator('#password').fill('fixture');
      await page.locator('#login-form button').click();
      await page.locator('#overview:visible').waitFor();
    };
    await login();
    assert.equal(await page.locator('nav .tab').count(), 4);
    for (const id of ['network','sms','settings','apps','settings']) {
      const link = id === 'apps' ? '#open-addons' : await page.locator('#apps').isVisible() ?
        '#back-settings' : '[data-page="' + id + '"]';
      await page.locator(link).click();
      assert.deepEqual(await page.locator('.page:visible').evaluateAll(nodes => nodes.map(n => n.id)), [id]);
      assert.equal(await page.locator('.tab[aria-current="page"]').getAttribute('data-page'), id === 'apps' ? 'settings' : id);
    }
    await page.locator('#time-read').click();
    await page.waitForFunction(() => document.getElementById('time-peers').value === 'office.example');
    await page.locator('#logout').click();
    assert.deepEqual(errors, []);
    await login();
    assert.equal(await page.locator('#time-peers').inputValue(), '');
    assert.equal(await page.locator('#time-fields').evaluate(node => node.disabled), true);
    assert.deepEqual(errors, []);
    assert.ok(calls.every(([, method]) => !['apply','install','save'].includes(method)));
    console.log('PASS Chromium: four tabs, single visible page, add-on subpage, logout/relogin and session-bound NTP form');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
