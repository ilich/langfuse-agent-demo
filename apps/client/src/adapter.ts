import type { ChatModelAdapter, ThreadMessage } from '@assistant-ui/react'

import { askAssistant } from './api'

/**
 * Sends the latest user message to the order assistant.
 *
 * The server is stateless and answers each message on its own, so earlier turns are not sent:
 * every message must identify the customer again (customer ID or contact name).
 */
export function createOrderAssistantAdapter(ask = askAssistant): ChatModelAdapter {
  return {
    async run({ messages, abortSignal }) {
      const message = latestUserText(messages)
      const answer = await ask(message, abortSignal)
      return { content: [{ type: 'text', text: answer }] }
    },
  }
}

export function latestUserText(messages: readonly ThreadMessage[]): string {
  const last = messages.findLast((m) => m.role === 'user')
  if (last === undefined) {
    throw new Error('There is no user message to send')
  }
  return last.content
    .flatMap((part) => (part.type === 'text' ? [part.text] : []))
    .join('\n')
    .trim()
}
