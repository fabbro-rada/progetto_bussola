import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { ConfirmDialog } from './ConfirmDialog'

test('confirm and cancel fire the right callbacks', async () => {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  renderWithProviders(<ConfirmDialog message="Disabilitare «x»?" confirmLabel="Conferma" onConfirm={onConfirm} onCancel={onCancel} />)
  expect(screen.getByText('Disabilitare «x»?')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
  expect(onCancel).toHaveBeenCalledOnce()
  await userEvent.click(screen.getByRole('button', { name: 'Conferma' }))
  expect(onConfirm).toHaveBeenCalledOnce()
})
