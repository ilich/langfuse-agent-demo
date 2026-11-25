/** Client for the order assistant server (apps/server). */

type FetchFn = typeof fetch

/** Sends one customer message to `POST /orders/assist` and returns the crew's answer. */
export async function askAssistant(
  message: string,
  signal?: AbortSignal,
  fetchFn: FetchFn = fetch,
): Promise<string> {
  const response = await fetchFn('/orders/assist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(errorMessage(response.status, body))
  }
  if (!isRecord(body) || typeof body.answer !== 'string') {
    throw new Error('The server returned an unexpected response')
  }
  return body.answer
}

/** Whether `GET /health` reports the server and its database as up. */
export async function checkHealth(fetchFn: FetchFn = fetch): Promise<boolean> {
  try {
    const response = await fetchFn('/health')
    return response.ok
  } catch {
    return false
  }
}

function errorMessage(status: number, body: unknown): string {
  // 503 {"error": "..."} when the crew can't run; 422 {"detail": [...]} for invalid input.
  if (isRecord(body) && typeof body.error === 'string') {
    return body.error
  }
  if (isRecord(body) && typeof body.detail === 'string') {
    return body.detail
  }
  return `The server responded with HTTP ${status}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
