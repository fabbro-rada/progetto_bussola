import { render, screen } from '@testing-library/react'
import { App } from './App'

test('renders the operator portal shell', () => {
  render(<App />)
  expect(screen.getByText('Bussola — Portale operatore')).toBeInTheDocument()
})
