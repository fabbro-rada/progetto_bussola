import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import { SkillBadge } from './SkillBadge'

test('renders the evidence grade word for each level', () => {
  renderWithProviders(
    <>
      <SkillBadge grade="certified" />
      <SkillBadge grade="demonstrated" />
      <SkillBadge grade="stated" />
    </>,
  )
  expect(screen.getByText(/Certificata/)).toBeInTheDocument()
  expect(screen.getByText(/Dimostrata/)).toBeInTheDocument()
  expect(screen.getByText(/Dichiarata/)).toBeInTheDocument()
})
