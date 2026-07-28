import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { LanguagePicker } from './LanguagePicker'

test('shows all five endonyms and reports the chosen code', async () => {
  const onSelect = vi.fn()
  renderWithProviders(<LanguagePicker onSelect={onSelect} />)
  for (const name of ['Italiano', 'English', 'Français', 'Español', 'العربية']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  await userEvent.click(screen.getByRole('button', { name: 'العربية' }))
  expect(onSelect).toHaveBeenCalledWith('ar')
})

// The French (siwis) Piper voice is CC BY 4.0, which REQUIRES visible
// attribution (creator, title, licence + link, and an indication the material
// was modified). This is the person-facing discharge of that obligation (§3).
test('shows the required CC BY attribution for the French (siwis) voice', () => {
  renderWithProviders(<LanguagePicker onSelect={vi.fn()} />)
  const credits = screen.getByRole('contentinfo')
  const text = credits.textContent ?? ''
  expect(text).toMatch(/SIWIS/)
  expect(text).toMatch(/University of Edinburgh/)
  expect(text).toMatch(/CC BY 4\.0/)
  expect(text).toMatch(/modified/i) // CC BY: must indicate the material was changed
  expect(text).toMatch(/creativecommons\.org\/licenses\/by\/4\.0/)
  expect(text).toMatch(/CREDITS\.md/) // pointer to the full third-party credits
  // the licence URL is plain text, not a navigable link (kiosk is locked, §7.1)
  expect(within(credits).queryByRole('link')).toBeNull()
})
