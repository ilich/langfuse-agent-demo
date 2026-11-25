import {
  AssistantRuntimeProvider,
  AuiIf,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
} from '@assistant-ui/react'
import { MarkdownTextPrimitive } from '@assistant-ui/react-markdown'
import { useEffect, useMemo, useState } from 'react'

import { createOrderAssistantAdapter } from './adapter'
import { checkHealth } from './api'

// Test prompts from apps/server/README.md (with CURRENT_DATE=2023-11-20).
const SUGGESTIONS = [
  'I am Carine Schmitt from France Restauration. I want to refund order 14288. It arrived too late',
  'I am Karin Josephs from Toms Spezialitäten. Can I get a refund for order 12544?',
  'Roland Mendel, Ernst Handel: refund order 11008',
  "I'm Maria Anders, show me order 13789",
]

export default function App() {
  const adapter = useMemo(() => createOrderAssistantAdapter(), [])
  const runtime = useLocalRuntime(adapter)

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="app">
        <Header />
        <Thread />
      </div>
    </AssistantRuntimeProvider>
  )
}

function Header() {
  const [healthy, setHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    let active = true
    const check = () => checkHealth().then((ok) => active && setHealthy(ok))
    void check()
    const timer = setInterval(check, 10_000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const label = healthy === null ? 'Checking server…' : healthy ? 'Server online' : 'Server offline'
  return (
    <header className="header">
      <h1>Order assistant</h1>
      <span className={`status status-${healthy === null ? 'unknown' : healthy ? 'up' : 'down'}`}>
        {label}
      </span>
    </header>
  )
}

function Thread() {
  return (
    <ThreadPrimitive.Root className="thread">
      <ThreadPrimitive.Viewport className="viewport">
        <AuiIf condition={(s) => s.thread.isEmpty}>
          <Welcome />
        </AuiIf>

        <ThreadPrimitive.Messages>
          {({ message }) => (message.role === 'user' ? <UserMessage /> : <AssistantMessage />)}
        </ThreadPrimitive.Messages>

        <AuiIf condition={(s) => s.thread.isRunning}>
          <p className="thinking">The crew is working on it… this can take a minute.</p>
        </AuiIf>

        <ThreadPrimitive.ViewportFooter className="footer">
          <Composer />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  )
}

function Welcome() {
  return (
    <div className="welcome">
      <p>
        Ask about an order or a refund. Each message is answered on its own, so always say who you
        are (customer ID or contact name).
      </p>
      <div className="suggestions">
        {SUGGESTIONS.map((prompt) => (
          <ThreadPrimitive.Suggestion key={prompt} prompt={prompt} send className="suggestion">
            {prompt}
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message message-user">
      <div className="bubble">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="message message-assistant">
      <div className="bubble">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
        <MessagePrimitive.Error>
          <ErrorPrimitive.Root className="error">
            <ErrorPrimitive.Message />
          </ErrorPrimitive.Root>
        </MessagePrimitive.Error>
      </div>
    </MessagePrimitive.Root>
  )
}

// The crew answers in Markdown (bold, lists).
function MarkdownText() {
  return <MarkdownTextPrimitive className="markdown" />
}

function Composer() {
  return (
    <ComposerPrimitive.Root className="composer">
      <ComposerPrimitive.Input
        className="composer-input"
        placeholder="e.g. I am Carine Schmitt from France Restauration…"
        rows={1}
        autoFocus
      />
      <AuiIf condition={(s) => !s.thread.isRunning}>
        <ComposerPrimitive.Send className="button">Send</ComposerPrimitive.Send>
      </AuiIf>
      <AuiIf condition={(s) => s.thread.isRunning}>
        <ComposerPrimitive.Cancel className="button button-secondary">Stop</ComposerPrimitive.Cancel>
      </AuiIf>
    </ComposerPrimitive.Root>
  )
}
