// server.py hands out a per-run token with every /api/state reply; POSTs must echo it.
let token = ''
const initialUrl = new URL(window.location.href)
let ownerCode = initialUrl.searchParams.get('owner')
if (ownerCode) {
  initialUrl.searchParams.delete('owner')
  window.history.replaceState(null, '', initialUrl.pathname + initialUrl.search + initialUrl.hash)
}

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
  if (path === '/api/state' && data.multiplayer && ownerCode) {
    const code = ownerCode
    ownerCode = null
    return api<T>('/api/host', { code })
  }
  return data
}
