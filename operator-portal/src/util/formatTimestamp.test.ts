import { expect, test } from 'vitest'
import { formatTimestamp } from './formatTimestamp'

test('renders an ISO instant as «YYYY-MM-DD HH:MM» (identical to the prior inline slice)', () => {
  expect(formatTimestamp('2026-07-27T10:00:00Z')).toBe('2026-07-27 10:00')
  expect(formatTimestamp('2026-01-02T23:45:59Z')).toBe('2026-01-02 23:45')
})
