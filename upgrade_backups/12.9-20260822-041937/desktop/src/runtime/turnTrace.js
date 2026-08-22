export function normalizeTurnTrace(value) {
  if (!value || typeof value !== 'object') return {};
  const timings = value.timings && typeof value.timings === 'object' ? value.timings : {};
  return { ...value, timings: { ...timings } };
}

export function formatMilliseconds(value, fallback = '—') {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 1 : 2)} s`;
  return `${Math.round(number)} ms`;
}

export function timingValue(trace, key) {
  const value = trace?.timings?.[key];
  return Number.isFinite(Number(value)) ? Number(value) : null;
}

export function providerAttemptSummary(trace) {
  const attempts = Array.isArray(trace?.attempts) ? trace.attempts : [];
  if (!attempts.length) return 'No provider attempts recorded';
  return attempts.map((item) => {
    const call = Number.isFinite(Number(item?.call_ms)) ? ` · ${formatMilliseconds(item.call_ms)}` : '';
    return `${item?.provider || 'unknown'}:${item?.status || 'unknown'}${call}`;
  }).join(' → ');
}
