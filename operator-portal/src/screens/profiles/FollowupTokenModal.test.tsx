import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { FollowupTokenModal } from './FollowupTokenModal'

test('shows the token + warning, copy calls the seam, close fires onClose', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()
  renderWithProviders(<FollowupTokenModal token="FUP-9K2M-7QRT" subtitle="Follow-up per «P-4F2A»." onClose={onClose} copy={copy} />)
  expect(screen.getByText('FUP-9K2M-7QRT')).toBeInTheDocument()
  expect(screen.getByText(/Mostrato una sola volta/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Copia' }))
  expect(copy).toHaveBeenCalledWith('FUP-9K2M-7QRT')
  expect(await screen.findByRole('button', { name: 'Copiato' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(onClose).toHaveBeenCalledOnce()
})

test('a failed copy does not flip the button to «Copiato»', async () => {
  const copy = vi.fn().mockRejectedValue(new Error('no clipboard'))
  renderWithProviders(<FollowupTokenModal token="FUP-9K2M-7QRT" subtitle="x" onClose={() => {}} copy={copy} />)
  await userEvent.click(screen.getByRole('button', { name: 'Copia' }))
  expect(copy).toHaveBeenCalledWith('FUP-9K2M-7QRT')
  expect(screen.getByRole('button', { name: 'Copia' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Copiato' })).not.toBeInTheDocument()
})

test('is an accessible dialog labelled by its own title', async () => {
  renderWithProviders(<FollowupTokenModal token="FUP-9K2M-7QRT" subtitle="x" onClose={() => {}} copy={vi.fn()} />)
  const dialog = screen.getByRole('dialog')
  const labelledBy = dialog.getAttribute('aria-labelledby')
  expect(labelledBy).toBeTruthy()
  expect(document.getElementById(labelledBy as string)).toHaveTextContent('Codice di follow-up')
})
