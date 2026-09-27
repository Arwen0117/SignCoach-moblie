import test from 'node:test';
import assert from 'node:assert/strict';
import { canonicalWord, createApi, decisionText, diagnosticText } from '../src/practice/api.js';
import { captureFrame, createRecorder } from '../src/practice/recorder.js';

const result = (decision = 'pass') => ({ attempt_id: 'attempt', target_word: 'MOM', decision, score: decision === 'rerecord' ? null : 42, quality_valid: decision !== 'rerecord', diagnostics: [], nearest_confusion: null, model_version: 'manual-baseline-v1', latency_ms: 12 });
const response = (data, status = 200) => new Response(status === 204 ? null : JSON.stringify(data), { status });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

test('canonical aliases', () => {
  assert.equal(canonicalWord('mother'), 'MOM'); assert.equal(canonicalWord('FATHER'), 'DAD');
  assert.equal(canonicalWord('thank you'), 'THANKYOU'); assert.equal(canonicalWord('THANKYOU'), 'THANKYOU');
});
test('204 body is never parsed, JPEG sent raw with canonical query', async () => {
  const blob = new Blob(['jpeg'], { type: 'image/jpeg' });
  const api = createApi(async (url, options) => {
    assert.match(url, /^\/api\/practice\/frame\?/);
    const query = new URL(url, 'http://test').searchParams;
    assert.equal(query.get('target_word'), 'MOM'); assert.equal(query.get('final'), 'false');
    assert.equal(options.body, blob); assert.equal(options.headers['Content-Type'], 'image/jpeg');
    return { ok: true, status: 204, json() { throw new Error('must not parse'); } };
  });
  assert.equal(await api.frame('attempt', 'MOTHER', false, blob), null);
});
for (const decision of ['pass', 'retry', 'rerecord']) {
  test(`terminal ${decision} is preserved regardless of score`, async () => {
    const terminal = result(decision);
    const api = createApi(async () => response(terminal));
    assert.deepEqual(await api.frame('attempt', 'MOM', true, new Blob()), terminal);
    assert.ok(decisionText[decision]);
    if (decision === 'rerecord') assert.equal(terminal.score, null);
  });
}
test('errors and mismatched responses never become a decision', async () => {
  for (const status of [400, 409, 422, 500]) {
    const api = createApi(async () => response({}, status));
    await assert.rejects(api.frame('attempt', 'MOM', true, new Blob()), new RegExp(String(status)));
  }
  for (const invalid of [{ ...result(), attempt_id: 'old' }, { ...result(), decision: 'unknown' }, { ...result(), score: null }, { ...result('rerecord'), score: 0 }]) {
    await assert.rejects(createApi(async () => response(invalid)).frame('attempt', 'MOM', true, new Blob()), /Invalid/);
  }
});
test('friendly diagnostics are limited to two and use returned confusion word', () => {
  const texts = diagnosticText({ diagnostics: [{ code: 'LOW_MATCH' }, { code: 'NEAREST_CONFUSION' }, { code: 'TOO_FEW_FRAMES' }], nearest_confusion: 'DAD' });
  assert.equal(texts.length, 2); assert.match(texts[1], /DAD/);
  for (const code of ['HANDS_NOT_VISIBLE', 'TOO_FEW_FRAMES', 'MOTION_NOT_DETECTED']) assert.equal(diagnosticText({ diagnostics: [{ code }] }).length, 1);
  assert.deepEqual(diagnosticText(result()), []);
});
test('recent attempts are re-read after feedback; 204 PATCH supported', async () => {
  let useful = null; const calls = [];
  const api = createApi(async (url, options) => {
    calls.push(url);
    if (options.method === 'PATCH') { useful = JSON.parse(options.body).useful; return response(null, 204); }
    return response({ attempts: [{ ...result(), feedback_useful: useful }] });
  });
  assert.equal((await api.attempts()).attempts[0].feedback_useful, null);
  await api.feedback('attempt', true);
  assert.equal((await api.attempts()).attempts[0].feedback_useful, true);
  assert.equal(calls[0], '/api/attempts?limit=20');
  assert.equal(calls[1], '/api/attempts/attempt/feedback');
});
test('recorder samples without queue, waits for slow request then sends one final', async () => {
  let clock = 0, inflight = 0, max = 0; const sends = [], results = [];
  const recorder = createRecorder({ uuid: () => 'attempt', now: () => clock, sleep: async ms => { clock += ms; }, capture: async () => new Blob(),
    api: { async frame(id, word, final) { inflight++; max = Math.max(max, inflight); sends.push({ clock, final }); clock += 750; await Promise.resolve(); inflight--; return final ? result() : null; } },
    onState() {}, onError: err => { throw err; }, onResult: value => results.push(value) });
  const first = recorder.start('MOM'); await recorder.start('MOM'); await first;
  assert.equal(max, 1); assert.equal(sends.filter(item => item.final).length, 1);
  assert.ok(sends.at(-1).clock >= 4000); assert.equal(results.length, 1);
});
test('cancel aborts old fetch and ignores a late response after a new attempt starts', async () => {
  const old = deferred(); let count = 0; let oldSignal; const received = [];
  const recorder = createRecorder({ duration: 0, capture: async () => new Blob(), uuid: () => `id-${++count}`,
    api: { frame(id, word, final, blob, signal) { if (id === 'id-1') { oldSignal = signal; return old.promise; } return Promise.resolve({ ...result(), attempt_id: id }); } },
    onState() {}, onError: err => { throw err; }, onResult: value => received.push(value.attempt_id) });
  const first = recorder.start('MOM'); await Promise.resolve(); recorder.cancel();
  assert.equal(oldSignal.aborted, true);
  await recorder.start('MOM'); old.resolve(result()); await first;
  assert.deepEqual(received, ['id-2']);
});
test('cancellation during encoding prevents a frame request', async () => {
  const encoding = deferred(); let calls = 0;
  const recorder = createRecorder({ capture: () => encoding.promise, api: { frame() { calls++; } }, onState() {}, onResult() {}, onError() {} });
  const run = recorder.start('MOM'); recorder.cancel(); encoding.resolve(new Blob()); await run; assert.equal(calls, 0);
});
test('capture uses at most 640 pixels longest edge and async JPEG 0.72', async () => {
  const canvas = { getContext: () => ({ drawImage() {} }), toBlob(callback, type, quality) { assert.equal(type, 'image/jpeg'); assert.equal(quality, 0.72); callback(new Blob()); } };
  await captureFrame({ videoWidth: 1920, videoHeight: 1080 }, canvas);
  assert.equal(canvas.width, 640); assert.equal(canvas.height, 360);
  await assert.rejects(captureFrame({ videoWidth: 0 }, canvas), /Camera is not ready/);
});
