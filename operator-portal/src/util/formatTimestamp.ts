// Compact display of an ISO timestamp as «YYYY-MM-DD HH:MM».
// NOTE: keeps the exact behavior of the prior inline slice (no timezone
// indicator — a TZ-aware formatter is a separate follow-up).
export function formatTimestamp(iso: string): string {
  return iso.replace('T', ' ').slice(0, 16)
}
