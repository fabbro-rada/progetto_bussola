import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { TextSizeProvider, useTextSize } from './TextSize'

function Probe() {
  const { size, setSize } = useTextSize()
  return (
    <div>
      <span>size:{size}</span>
      <button onClick={() => setSize('xlarge')}>bigger</button>
    </div>
  )
}

test('default is normal (scale 1) and setSize updates the CSS variable', async () => {
  render(
    <TextSizeProvider>
      <Probe />
    </TextSizeProvider>,
  )
  expect(screen.getByText('size:normal')).toBeInTheDocument()
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1')

  await userEvent.click(screen.getByText('bigger'))
  expect(screen.getByText('size:xlarge')).toBeInTheDocument()
  expect(document.documentElement.style.getPropertyValue('--text-scale')).toBe('1.5')
})
