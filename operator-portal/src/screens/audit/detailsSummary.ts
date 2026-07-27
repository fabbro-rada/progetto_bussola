export function detailsSummary(details: Record<string, unknown>): string {
  const parts = Object.entries(details).map(([k, v]) => `${k}=${String(v)}`)
  return parts.length > 0 ? parts.join(', ') : '—'
}
