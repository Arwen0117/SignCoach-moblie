// Run after build. PLAYWRIGHT_MODULE can point to an existing read-only installation.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = resolve(process.env.DEMO_BUILD_DIR || 'build');
const server = createServer(async (req, res) => {
  try {
    const path = resolve(root, `.${new URL(req.url, 'http://test').pathname === '/' ? '/index.html' : new URL(req.url, 'http://test').pathname}`);
    if (!path.startsWith(root)) { res.writeHead(403).end(); return; }
    const content = await readFile(path);
    res.setHeader('Content-Type', ({ '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' })[extname(path)] || 'application/octet-stream');
    res.end(content);
  } catch { res.writeHead(404).end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
try {
  const context = await browser.newContext({ permissions: ['camera'], viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const failures = []; page.on('pageerror', error => failures.push(error.message));
  const labels = JSON.parse(await readFile(fileURLToPath(new URL('../../signcoach_benchmark/vocabulary.json', import.meta.url)), 'utf8')).words.map(item => item.target_word);
  const attempts = []; const frames = []; let decision = 'pass', reads = 0, inflight = 0, maxInflight = 0, frameDelay = 380, terminalDelay = 150;
  const frameRequest = req => req.url().includes('/api/practice/frame?');
  page.on('request', req => { if (frameRequest(req)) { inflight++; maxInflight = Math.max(maxInflight, inflight); } });
  page.on('requestfinished', req => { if (frameRequest(req)) inflight--; });
  page.on('requestfailed', req => { if (frameRequest(req)) inflight--; });
  await page.route('**/api/**', async route => {
    const req = route.request(), url = new URL(req.url());
    const json = data => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
    if (url.pathname === '/api/labels') return json({ labels });
    if (url.pathname === '/api/attempts') { reads++; return json({ attempts }); }
    if (url.pathname.endsWith('/feedback')) { attempts.find(item => url.pathname.includes(item.attempt_id)).feedback_useful = req.postDataJSON().useful; return route.fulfill({ status: 204 }); }
    if (url.pathname.includes('/signasl/video/')) return json({ video_url: null });
    if (url.pathname === '/api/practice/frame') {
      const final = url.searchParams.get('final') === 'true';
      assert.equal(req.headers()['content-type'], 'image/jpeg');
      assert.equal(req.postDataBuffer()[0], 0xff); assert.equal(req.postDataBuffer()[1], 0xd8);
      const id = url.searchParams.get('attempt_id'); assert.match(id, /^[0-9a-f-]{36}$/);
      frames.push({ id, final, at: Date.now(), target: url.searchParams.get('target_word') });
      await new Promise(done => setTimeout(done, final ? terminalDelay : frameDelay));
      if (!final) return route.fulfill({ status: 204 }).catch(() => {});
      const item = { attempt_id: id, target_word: url.searchParams.get('target_word'), decision, score: decision === 'rerecord' ? null : decision === 'pass' ? 42 : 99, quality_valid: decision !== 'rerecord', diagnostics: decision === 'pass' ? [] : [{ code: decision === 'retry' ? 'LOW_MATCH' : 'HANDS_NOT_VISIBLE', severity: 'warning' }, { code: 'NEAREST_CONFUSION', severity: 'warning' }, { code: 'TOO_FEW_FRAMES', severity: 'warning' }], nearest_confusion: 'DAD', model_version: 'manual-baseline-v1', latency_ms: 150, created_at: new Date().toISOString(), feedback_useful: null };
      attempts.unshift(item); return json(item).catch(() => {});
    }
    return route.fulfill({ status: 404 });
  });
  // Old local results must have no influence on the new UI.
  await page.addInitScript(() => localStorage.setItem('signlearn-progress-v2', JSON.stringify({ wordStats: { hello: { bestScore: 100, passes: 100 } } })));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByRole('button', { name: 'Start practice', exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('#practice-word option').length === 30);
  await page.getByRole('button', { name: 'Enable camera', exact: true }).click();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(el => el.textContent === 'Start recording' && !el.disabled));
  for (const [outcome, title] of [['pass', 'Match passed'], ['retry', 'Try again'], ['rerecord', 'Please record again']]) {
    decision = outcome;
    const before = frames.length, beforeReads = reads;
    await page.getByLabel('Practice word').selectOption(outcome === 'pass' ? 'MOM' : 'THANKYOU');
    await page.getByRole('button', { name: 'Start recording', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Start recording', exact: true }).isDisabled(), true);
    await page.getByRole('heading', { name: title, exact: true }).waitFor({ timeout: 12000 });
    const sent = frames.slice(before);
    assert.equal(sent.filter(item => item.final).length, 1);
    assert.ok(sent.at(-1).at - sent[0].at >= 3900);
    assert.ok(sent.every(item => item.target === (outcome === 'pass' ? 'MOM' : 'THANKYOU')));
    await page.waitForFunction(count => document.querySelectorAll('li time').length === count, attempts.length);
    assert.ok(reads > beforeReads);
    if (outcome === 'rerecord') assert.equal(await page.getByRole('heading', { name: title, exact: true }).locator('..').getByText('Similarity score:', { exact: false }).count(), 0);
    if (outcome !== 'pass') assert.equal(await page.getByRole('heading', { name: title, exact: true }).locator('..').locator('li').count(), 2);
  }
  await page.getByRole('button', { name: 'Helpful', exact: true }).first().click();
  await page.getByRole('button', { name: 'Helpful ✓', exact: true }).waitFor();
  assert.equal(attempts[0].feedback_useful, true);
  assert.ok(await page.locator('canvas').evaluate(el => Math.max(el.width, el.height) <= 640));
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await page.getByRole('button', { name: 'Start recording', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.waitForTimeout(500);
  assert.equal(await page.getByRole('heading', { name: 'Match passed', exact: true }).count(), 0);
  // A target change cancels an outstanding request and clears the result.
  frameDelay = 900;
  await page.getByRole('button', { name: 'Start recording', exact: true }).click();
  await page.waitForTimeout(150);
  await page.getByLabel('Practice word').selectOption('DAD');
  await page.waitForTimeout(1000);
  assert.equal(await page.getByRole('button', { name: 'Start recording', exact: true }).isEnabled(), true);
  assert.equal(await page.getByRole('heading', { name: 'Please record again', exact: true }).count(), 0);
  // Navigation must release the camera and suppress outstanding results.
  await page.getByRole('button', { name: 'Start recording', exact: true }).click();
  await page.waitForTimeout(100);
  await page.getByRole('button', { name: 'Courses', exact: true }).first().click();
  await page.getByText('Lecture 4: Family 1', { exact: true }).click();
  await page.getByRole('button', { name: /^mother /i }).click();
  await page.getByRole('heading', { name: 'mother', exact: true }).waitFor();
  await page.getByRole('link', { name: 'Open SignASL', exact: true }).waitFor();
  assert.deepEqual(failures, []);
  assert.equal(maxInflight, 1);
  console.log(JSON.stringify({ result: 'passed', terminalDecisions: 3, maxInflight, attemptsReads: reads, totalFrames: frames.length, camera: 'Chromium fake device', coursesAndReferenceLink: 'clickable' }, null, 2));
} finally { await browser.close(); await new Promise(done => server.close(done)); }
