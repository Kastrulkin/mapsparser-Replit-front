const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(path.join(process.cwd(), 'frontend/node_modules/playwright'));

async function main() {
  const destination = path.join(process.cwd(), 'outputs/localos-release-20260906');
  const manifest = JSON.parse(fs.readFileSync(path.join(destination, 'release-manifest.json'), 'utf8'));
  const entry = fs.readFileSync('frontend/dist/index.html', 'utf8');
  const match = entry.match(/src="(\/assets\/index-[^"]+\.js)"/);
  if (!match) throw new Error('App entry module missing');
  const modulePath = match[1];
  const expectedHash = manifest.files['frontend/dist' + modulePath];
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const viewport of [{ width: 1440, height: 960 }, { width: 393, height: 852 }]) {
      const context = await browser.newContext({ viewport, locale: 'ru-RU' });
      const page = await context.newPage();
      const errors = [];
      const blockedWrites = [];
      const moduleChecks = [];
      await page.route('**/*', async route => {
        const request = route.request();
        if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          blockedWrites.push({ method: request.method(), path: new URL(request.url()).pathname });
          await route.abort();
          return;
        }
        await route.continue();
      });
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => {
        if (new URL(response.url()).pathname === modulePath) {
          moduleChecks.push(response.body().then(body => ({ status: response.status(), hash: crypto.createHash('sha256').update(body).digest('hex') })));
        }
      });
      await page.addInitScript(() => localStorage.setItem('language', 'ru'));
      const response = await page.goto('https://localos.pro/dashboard/today', { waitUntil: 'networkidle', timeout: 45000 });
      await page.waitForURL(url => url.pathname.includes('login'), { timeout: 15000 });
      await page.locator('input[type="password"]').waitFor({ state: 'visible', timeout: 15000 });
      const checks = await Promise.all(moduleChecks);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      const passwordFields = await page.locator('input[type="password"]').count();
      await page.screenshot({ path: path.join(destination, 'production-public-' + viewport.width + '.png'), fullPage: true });
      const result = { viewport, initial_status: response.status(), final_path: new URL(page.url()).pathname, login_form_visible: passwordFields > 0, authenticated: false, live_module_verified: checks.some(check => check.status === 200 && check.hash === expectedHash), page_errors: errors, document_overflow: overflow, blocked_writes: blockedWrites };
      results.push(result);
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const passed = results.every(result => result.initial_status === 200 && result.login_form_visible && result.live_module_verified && result.page_errors.length === 0 && !result.document_overflow);
  const report = { status: passed ? 'PASS' : 'FAIL', scope: 'Public browser and protected-route login boundary only; no authenticated session or user data', release_commit: manifest.commit, results };
  fs.writeFileSync(path.join(destination, 'production-public-browser.json'), JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify(report) + '\n');
  if (!passed) process.exitCode = 1;
}
main().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
