export function captureFrame(video, canvas) {
  if (!video.videoWidth || !video.videoHeight) return Promise.reject(new Error('Camera is not ready. Please try again.'));
  const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Could not capture the camera frame.')), 'image/jpeg', 0.72));
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
// Each await completes before another frame is captured or sent; there is no queue.
export function createRecorder({ api, capture, onState, onResult, onError, now = () => performance.now(), sleep = pause, duration = 4000, interval = 300, uuid = () => crypto.randomUUID() }) {
  let generation = 0;
  let controller;
  let busy = false;
  function cancel() { generation++; controller?.abort(); busy = false; }
  return {
    cancel,
    async start(word) {
      if (busy) return;
      busy = true;
      const current = ++generation;
      controller = new AbortController();
      const signal = controller.signal;
      const id = uuid();
      const active = () => current === generation && !signal.aborted;
      const started = now();
      onState({ phase: 'recording', elapsed: 0 });
      try {
        while (active()) {
          const tick = now();
          const final = tick - started >= duration;
          onState({ phase: final ? 'analyzing' : 'recording', elapsed: Math.min(duration, tick - started) });
          const blob = await capture();
          if (!active()) return;
          const result = await api.frame(id, word, final, blob, signal);
          if (!active()) return;
          if (result) { onResult(result); return; }
          if (final) throw new Error('Analysis returned no result. Please record again.');
          await sleep(Math.max(0, interval - (now() - tick)));
        }
      } catch (error) {
        if (active()) onError(error);
      } finally {
        if (active()) { busy = false; onState({ phase: 'idle', elapsed: 0 }); }
      }
    },
  };
}
