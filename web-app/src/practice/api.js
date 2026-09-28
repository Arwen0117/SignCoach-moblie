import { apiUrl } from "../apiUrl.js";

export const canonicalWord = word => ({ MOTHER: 'MOM', FATHER: 'DAD', 'THANK YOU': 'THANKYOU', 'THANK-YOU': 'THANKYOU' }[word.toUpperCase()] ?? word.toUpperCase());
export const decisionText = { pass: 'Match passed', retry: 'Try again', rerecord: 'Please record again' };
export function diagnosticText(result) {
  const messages = {
    HANDS_NOT_VISIBLE: 'Hands were not clear enough. Please keep your hands visible in the frame.',
    TOO_FEW_FRAMES: 'Too few frames were collected. Please record again.',
    MOTION_NOT_DETECTED: 'No clear movement was detected. Please perform the complete sign.',
    LOW_MATCH: 'Similarity to the reference was low. Try watching the demonstration again.',
    NEAREST_CONFUSION: `This attempt was closer to ${result.nearest_confusion ?? 'another sign'}. Compare the demonstrations.`,
  };
  return (result.diagnostics ?? []).slice(0, 2).map(item => messages[item.code]).filter(Boolean);
}
export function createApi(fetcher = globalThis.fetch) {
  async function request(path, options = {}) {
    const response = await fetcher(apiUrl(path), options);
    if (!response.ok) throw new Error(`Request failed (${response.status}). Please try again.`);
    return response.status === 204 ? null : response.json();
  }
  return {
    labels: signal => request('/api/labels', { signal }),
    attempts: signal => request('/api/attempts?limit=20', { signal }),
    feedback: (id, useful, signal) => request(`/api/attempts/${encodeURIComponent(id)}/feedback`, { method: 'PATCH', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ useful }) }),
    async frame(id, word, final, blob, signal) {
      const query = new URLSearchParams({ attempt_id: id, target_word: canonicalWord(word), final: String(final) });
      const result = await request(`/api/practice/frame?${query}`, { method: 'POST', signal, headers: { 'Content-Type': 'image/jpeg' }, body: blob });
      if (result && (!decisionText[result.decision] || result.attempt_id !== id || result.target_word !== canonicalWord(word) || (result.decision === 'rerecord' ? result.score !== null : typeof result.score !== 'number' || result.score < 0 || result.score > 100))) throw new Error('Invalid recording response. Please try again.');
      return result;
    },
  };
}
export const api = createApi();
