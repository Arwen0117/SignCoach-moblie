import React, { useEffect, useRef, useState } from 'react';
import { api, canonicalWord, decisionText, diagnosticText } from './api.js';
import { captureFrame, createRecorder } from './recorder.js';

const button = 'rounded-lg border border-blue-200 px-4 py-2 font-semibold disabled:opacity-40';
export function AttemptsList({ revision = 0 }) {
  const [attempts, setAttempts] = useState([]);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [pending, setPending] = useState(null);
  const feedbackController = useRef(null);
  useEffect(() => () => feedbackController.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.attempts(controller.signal).then(data => { if (!controller.signal.aborted) setAttempts(data.attempts.slice(0, 20)); }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [revision, refresh]);
  async function feedback(id, useful) {
    if (pending) return;
    const controller = new AbortController();
    feedbackController.current = controller;
    setPending(id); setError('');
    try { await api.feedback(id, useful, controller.signal); if (!controller.signal.aborted) setRefresh(value => value + 1); }
    catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally { if (!controller.signal.aborted) setPending(null); }
  }
  return <section className="rounded-xl border border-blue-100 bg-white p-5">
    <div className="flex items-center justify-between"><h2 className="text-xl font-bold">Recent practice</h2><button className={button} onClick={() => setRefresh(value => value + 1)}>Refresh</button></div>
    {error && <p role="alert" className="my-3 text-red-700">{error}</p>}
    {!attempts.length && <p className="py-5 text-slate-500">No recent practice yet.</p>}
    <ul className="divide-y divide-slate-100">{attempts.map(item => <li key={item.attempt_id} className="flex flex-wrap items-center justify-between gap-3 py-4">
      <div><p className="font-bold">{item.target_word} · {item.score === null ? 'Please record again' : `Similarity score: ${item.score}/100`}</p><time className="text-sm text-slate-500">{new Date(item.created_at).toLocaleString()}</time></div>
      <div className="flex gap-2">{[true, false].map(useful => <button key={String(useful)} className={button} disabled={pending !== null} aria-pressed={item.feedback_useful === useful} onClick={() => feedback(item.attempt_id, useful)}>{useful ? 'Helpful' : 'Not helpful'}{item.feedback_useful === useful ? ' ✓' : ''}</button>)}</div>
    </li>)}</ul>
  </section>;
}

export default function PracticePage({ vocabulary, initialSign, ReferenceVideo }) {
  const [labels, setLabels] = useState([]);
  const [target, setTarget] = useState('');
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraPending, setCameraPending] = useState(false);
  const [state, setState] = useState({ phase: 'idle', elapsed: 0 });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [reload, setReload] = useState(0);
  const video = useRef(null), canvas = useRef(null), stream = useRef(null), alive = useRef(false), recorder = useRef(null);
  useEffect(() => {
    alive.current = true;
    recorder.current = createRecorder({ api, capture: () => captureFrame(video.current, canvas.current), onState: setState, onError: err => setError(err.message), onResult: value => { setResult(value); setRevision(value => value + 1); } });
    return () => { alive.current = false; recorder.current.cancel(); stream.current?.getTracks().forEach(track => track.stop()); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.labels(controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setLabels(data.labels);
      const preferred = canonicalWord(initialSign.gloss);
      setTarget(data.labels.includes(preferred) ? preferred : data.labels[0] ?? '');
    }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [initialSign, reload]);
  useEffect(() => { recorder.current?.cancel(); setState({ phase: 'idle', elapsed: 0 }); setResult(null); }, [target]);
  async function startCamera() {
    setCameraPending(true); setError('');
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (!alive.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media; video.current.srcObject = media;
      await video.current.play();
      if (alive.current) setCameraOn(true);
    } catch { if (alive.current) setError('Camera could not start. Allow camera access and try again.'); }
    finally { if (alive.current) setCameraPending(false); }
  }
  function reset() { recorder.current.cancel(); setState({ phase: 'idle', elapsed: 0 }); setResult(null); setError(''); }
  function changeTarget(value) { reset(); setTarget(value); }
  const sign = vocabulary.find(item => canonicalWord(item.gloss) === target);
  const busy = state.phase !== 'idle';
  return <section className="space-y-5">
    <div><p className="text-sm font-semibold text-blue-600">Guided practice</p><h1 className="text-3xl font-bold">Watch, record, repeat</h1><p className="mt-2 text-sm text-slate-500">Demo scoring cannot replace a sign language teacher's judgment.</p></div>
    <div className="flex flex-wrap items-center gap-3"><label htmlFor="practice-word" className="font-semibold">Practice word</label><select id="practice-word" className={button} value={target} onChange={event => changeTarget(event.target.value)} disabled={!labels.length}>{labels.map(word => <option key={word}>{word}</option>)}</select><button className={button} disabled={!labels.length} onClick={() => changeTarget(labels[(labels.indexOf(target) + 1) % labels.length])}>Skip</button>{!labels.length && <button className={button} onClick={() => setReload(value => value + 1)}>Reload words</button>}</div>
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-xl border border-blue-100 bg-white p-4"><h2 className="mb-3 text-lg font-bold">Reference · {sign?.word ?? target}</h2>{sign && <ReferenceVideo sign={sign} />}</div>
      <div className="rounded-xl border border-blue-100 bg-white p-4"><h2 className="mb-3 text-lg font-bold">Your camera</h2><video ref={video} muted playsInline className="aspect-video w-full rounded-lg bg-slate-900 object-contain" /><canvas ref={canvas} hidden />
        <div role="status" className="my-3 font-semibold">{state.phase === 'recording' ? `Recording · ${(state.elapsed / 1000).toFixed(1)} / 4 seconds` : state.phase === 'analyzing' ? 'Analyzing…' : cameraOn ? 'Ready for a 4-second recording' : 'Enable your camera to begin'}</div>
        <div className="flex flex-wrap gap-2">{!cameraOn && <button className={button} disabled={cameraPending} onClick={startCamera}>{cameraPending ? 'Starting camera…' : 'Enable camera'}</button>}<button className={`${button} bg-blue-600 text-white`} disabled={!cameraOn || !target || busy} onClick={() => { setResult(null); setError(''); recorder.current.start(target); }}>Start recording</button><button className={button} onClick={reset}>{busy ? 'Cancel' : 'Reset'}</button></div>
      </div>
    </div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">Recording / connection error: {error}</p>}
    {result && <div role="status" className="rounded-xl border border-blue-200 bg-blue-50 p-5"><h2 className="text-2xl font-bold">{decisionText[result.decision]}</h2>{result.score !== null && <p className="mt-2 text-lg">Similarity score: {result.score}/100</p>}<ul className="mt-3 space-y-2">{diagnosticText(result).map(text => <li key={text}>{text}</li>)}</ul></div>}
    <AttemptsList revision={revision} />
  </section>;
}
