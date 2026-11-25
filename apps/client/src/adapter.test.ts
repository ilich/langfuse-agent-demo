import type { ChatModelRunOptions, ThreadMessage } from '@assistant-ui/react'
import { describe, expect, it, vi } from 'vitest'

import { createOrderAssistantAdapter, latestUserText } from './adapter'

function message(role: 'user' | 'assistant', ...texts: string[]): ThreadMessage {
  return {
    role,
    content: texts.map((text) => ({ type: 'text', text })),
  } as unknown as ThreadMessage
}

describe('latestUserText', () => {
  it('returns the text of the last user message', () => {
    const messages = [message('user', 'first'), message('assistant', 'reply'), message('user', ' second ')]

    expect(latestUserText(messages)).toBe('second')
  })

  it('joins multiple text parts', () => {
    expect(latestUserText([message('user', 'a', 'b')])).toBe('a\nb')
  })

  it('fails without a user message', () => {
    expect(() => latestUserText([message('assistant', 'hello')])).toThrow('no user message')
  })
})

describe('createOrderAssistantAdapter', () => {
  it('sends only the latest user message and returns the answer as text', async () => {
    const ask = vi.fn(async (msg: string) => `answer to ${msg}`)
    const adapter = createOrderAssistantAdapter(ask)
    const abortSignal = new AbortController().signal

    const result = await adapter.run({
      messages: [message('user', 'old'), message('assistant', 'x'), message('user', 'new')],
      abortSignal,
    } as unknown as ChatModelRunOptions)

    expect(ask).toHaveBeenCalledWith('new', abortSignal)
    expect(result).toEqual({ content: [{ type: 'text', text: 'answer to new' }] })
  })
})
