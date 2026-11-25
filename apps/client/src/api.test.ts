import { describe, expect, it, vi } from 'vitest'

import { askAssistant, checkHealth } from './api'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('askAssistant', () => {
  it('posts the message and returns the answer', async () => {
    const fetchFn = vi.fn(async () => jsonResponse(200, { answer: 'Refund approved' }))

    const answer = await askAssistant('Refund order 14288', undefined, fetchFn)

    expect(answer).toBe('Refund approved')
    expect(fetchFn).toHaveBeenCalledWith('/orders/assist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'Refund order 14288' }),
      signal: undefined,
    })
  })

  it('reports the server error when the crew cannot run', async () => {
    const fetchFn = vi.fn(async () =>
      jsonResponse(503, { error: 'OPENAI_API_KEY is not configured' }),
    )

    await expect(askAssistant('hi', undefined, fetchFn)).rejects.toThrow(
      'OPENAI_API_KEY is not configured',
    )
  })

  it('reports the HTTP status when the error body is not JSON', async () => {
    const fetchFn = vi.fn(async () => new Response('Bad gateway', { status: 502 }))

    await expect(askAssistant('hi', undefined, fetchFn)).rejects.toThrow('HTTP 502')
  })

  it('rejects a response without an answer', async () => {
    const fetchFn = vi.fn(async () => jsonResponse(200, { reply: 'x' }))

    await expect(askAssistant('hi', undefined, fetchFn)).rejects.toThrow('unexpected response')
  })
})

describe('checkHealth', () => {
  it('is true when the server responds OK', async () => {
    expect(await checkHealth(async () => jsonResponse(200, { status: 'ok' }))).toBe(true)
  })

  it('is false when the server is unreachable', async () => {
    const fetchFn = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    expect(await checkHealth(fetchFn)).toBe(false)
  })
})
