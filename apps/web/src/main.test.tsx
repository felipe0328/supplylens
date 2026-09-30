import { StrictMode } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'

const { createRoot, render } = vi.hoisted(() => ({
  createRoot: vi.fn(),
  render: vi.fn(),
}))

vi.mock('react-dom/client', () => ({ createRoot }))

beforeEach(() => {
  document.body.innerHTML = '<div id="root"></div>'
  createRoot.mockReturnValue({ render })
})

it('mounts the application in strict mode', async () => {
  await import('./main')

  expect(createRoot).toHaveBeenCalledWith(document.getElementById('root'))
  expect(render).toHaveBeenCalledOnce()
  expect(render.mock.calls[0][0].type).toBe(StrictMode)
})
