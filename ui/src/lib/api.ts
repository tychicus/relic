// server.py hands out a per-run token with every /api/state reply; POSTs must echo it.
let token = ''

export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Game-Token': token },
          body: JSON.stringify(body),
        },
  )
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || 'Connection error.')
  if (data.token) token = data.token
  return data
}
