import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import App from './App'

it('increments the counter when clicked', () => {
  render(<App />)

  const counter = screen.getByRole('button', { name: 'Count is 0' })
  fireEvent.click(counter)

  expect(screen.getByRole('button', { name: 'Count is 1' }).textContent).toBe(
    'Count is 1',
  )
})
