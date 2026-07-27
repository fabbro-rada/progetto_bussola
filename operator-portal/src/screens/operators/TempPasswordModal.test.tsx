import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { TempPasswordModal } from './TempPasswordModal'

test('shows the password + warning, copy calls the seam, close fires onClose', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  const onClose = vi.fn()
  renderWithProviders(<TempPasswordModal password="7Kq9-mZ2t-Rf4x" subtitle="Operatore «x» creato." onClose={onClose} copy={copy} />)
  expect(screen.getByText('7Kq9-mZ2t-Rf4x')).toBeInTheDocument()
  expect(screen.getByText(/Mostrata una sola volta/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Copia' }))
  expect(copy).toHaveBeenCalledWith('7Kq9-mZ2t-Rf4x')
  expect(await screen.findByRole('button', { name: 'Copiato' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Ho copiato, chiudi' }))
  expect(onClose).toHaveBeenCalledOnce()
})

test('a failed copy does not flip the button to «Copiato»', async () => {
  const copy = vi.fn().mockRejectedValue(new Error('no clipboard'))
  renderWithProviders(<TempPasswordModal password="7Kq9-mZ2t-Rf4x" subtitle="x" onClose={() => {}} copy={copy} />)
  await userEvent.click(screen.getByRole('button', { name: 'Copia' }))
  expect(copy).toHaveBeenCalledWith('7Kq9-mZ2t-Rf4x')
  expect(screen.getByRole('button', { name: 'Copia' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Copiato' })).not.toBeInTheDocument()
})
