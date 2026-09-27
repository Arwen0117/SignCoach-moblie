// Real local backend integration. Only Chromium's camera is synthetic; no routes are intercepted.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.DEMO_URL || 'http://127.0.0.1:8000';
const base = origin;
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
try {
  const context = await browser.newContext({ permissions: ['camera'], viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const failures = [], frames = [], intermediateStatuses = [], apiPaths = new Set(); let inflight = 0, maxInflight = 0, finalRequest;
  page.on('response', r => { if (r.url().includes('/api/practice/frame?') && new URL(r.url()).searchParams.get('final') === 'false') intermediateStatuses.push(r.status()); });
  page.on('pageerror', err => failures.push(err.message));
  page.on('request', req => {
    if (new URL(req.url()).pathname.startsWith('/api/')) { assert.equal(new URL(req.url()).origin, origin); apiPaths.add(new URL(req.url()).pathname); }
    if (!req.url().includes('/api/practice/frame?')) return;
    inflight++; maxInflight = Math.max(maxInflight, inflight);
    frames.push({ at: Date.now(), final: new URL(req.url()).searchParams.get('final') === 'true' });
    assert.equal(req.headers()['content-type'], 'image/jpeg');
    if (frames.at(-1).final) finalRequest = req;
  });
  for (const event of ['requestfinished', 'requestfailed']) page.on(event, req => { if (req.url().includes('/api/practice/frame?')) inflight--; });
  const health = await (await context.request.get(`${base}/api/health`)).json();
  assert.deepEqual(health, { ok: true, model_version: 'manual-baseline-v1' });
  for (const path of ['/api/missing', '/assets/missing.js', '/deploy/reference/index.npz', '/data/p7-demo.sqlite3', '/asl_realtime/api_server.py']) {
    const missing = await context.request.get(`${origin}${path}`);
    assert.equal(missing.status(), 404, path);
  }
  await page.goto(origin);
  for (const asset of await page.locator('script[src],link[rel="stylesheet"]').evaluateAll(nodes => nodes.map(n => n.src || n.href))) {
    assert.equal(new URL(asset).origin, origin);
    assert.equal((await context.request.get(asset)).status(), 200);
  }
  const labelsResponse = page.waitForResponse(r => r.url() === `${base}/api/labels`);
  await page.getByRole('button', { name: 'Start practice', exact: true }).click();
  const labels = (await (await labelsResponse).json()).labels;
  const vocabulary = JSON.parse(await readFile(new URL('../../signcoach_benchmark/vocabulary.json', import.meta.url), 'utf8')).words.map(w => w.target_word);
  assert.deepEqual(labels, vocabulary);
  await page.waitForFunction(() => document.querySelectorAll('#practice-word option').length === 30);
  await page.getByLabel('Practice word').selectOption('THANKYOU');
  await page.getByRole('button', { name: 'Enable camera', exact: true }).click();
  await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent === 'Start recording' && !b.disabled));
  const terminalResponse = page.waitForResponse(r => r.url().includes('/api/practice/frame?') && new URL(r.url()).searchParams.get('final') === 'true');
  const start = Date.now();
  await page.getByRole('button', { name: 'Start recording', exact: true }).click();
  const response = await terminalResponse;
  assert.equal(response.status(), 200);
  const result = await response.json();
  await page.getByRole('heading', { name: 'Please record again', exact: true }).waitFor();
  const elapsedMs = Date.now() - start;
  assert.equal(result.decision, 'rerecord'); assert.equal(result.score, null);
  assert.equal(result.quality_valid, false); assert.equal(result.target_word, 'THANKYOU');
  assert.equal(result.model_version, 'manual-baseline-v1');
  assert.ok(result.diagnostics.length <= 2); assert.ok(result.diagnostics.some(d => d.code === 'HANDS_NOT_VISIBLE'));
  assert.equal('match_probability' in result, false);
  assert.equal(frames.filter(f => f.final).length, 1); assert.equal(maxInflight, 1);
  assert.equal(intermediateStatuses.length, frames.length - 1);
  assert.ok(intermediateStatuses.every(status => status === 204));
  assert.ok(frames.at(-1).at - frames[0].at >= 3900);
  const dimensions = await page.locator('canvas').evaluate(c => [c.width, c.height]);
  assert.ok(Math.max(...dimensions) <= 640);
  await page.getByRole('button', { name: 'Not helpful', exact: true }).first().click();
  await page.getByRole('button', { name: 'Not helpful ✓', exact: true }).first().waitFor();
  await page.getByRole('button', { name: 'Helpful', exact: true }).first().click();
  await page.getByRole('button', { name: 'Helpful ✓', exact: true }).first().waitFor();
  const history = async () => (await (await context.request.get(`${base}/api/attempts?limit=100`)).json()).attempts;
  assert.equal((await history()).find(a => a.attempt_id === result.attempt_id).feedback_useful, true);
  const duplicateBytes = await page.locator('canvas').evaluate(c => new Promise(resolve => c.toBlob(async blob => resolve(Array.from(new Uint8Array(await blob.arrayBuffer()))), 'image/jpeg', 0.72)));
  assert.equal(Buffer.from(duplicateBytes).readUInt16BE(0), 0xffd8);
  await page.reload();
  await page.getByRole('button', { name: 'Helpful ✓', exact: true }).first().waitFor();
  assert.equal((await history()).filter(a => a.attempt_id === result.attempt_id).length, 1);
  const duplicate = await context.request.post(finalRequest.url(), { headers: { 'Content-Type': 'image/jpeg' }, data: Buffer.from(duplicateBytes) });
  assert.deepEqual(await duplicate.json(), result);
  assert.equal((await history()).filter(a => a.attempt_id === result.attempt_id).length, 1);
  assert.deepEqual(failures, []);
  const evidence = { input: 'Chromium fake camera; no human, no hands; real JPEG/MediaPipe/index/SQLite; no API interception', origin, apiPaths: [...apiPaths], staticAndApi404: true, health, labels, result, elapsedMs, finalRequestMs: finalRequest.timing().responseEnd, frames: frames.length, intermediateStatuses, maxInflight, dimensions, feedback: true, reloadPersisted: true, duplicateCount: 1 };
  if (process.env.DEMO_EVIDENCE_PATH) await writeFile(process.env.DEMO_EVIDENCE_PATH, JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
} finally { await browser.close(); }
