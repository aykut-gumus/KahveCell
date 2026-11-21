const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

function notifyAuthChange() {
  window.dispatchEvent(new Event('kahvecell:auth-change'))
}

export function saveSession(tokens) {
  localStorage.setItem('kahvecell_access_token', tokens.access_token)
  localStorage.setItem('kahvecell_refresh_token', tokens.refresh_token)
  localStorage.setItem('kahvecell_user', JSON.stringify(tokens.user))
}

export function clearSession() {
  localStorage.removeItem('kahvecell_access_token')
  localStorage.removeItem('kahvecell_refresh_token')
  localStorage.removeItem('kahvecell_user')
  notifyAuthChange()
}

async function readResponse(response) {
  if (response.status === 204) return null
  if (response.headers.get('content-type')?.includes('application/json')) {
    return response.json()
  }
  return response.text()
}

async function sendRequest(path, options, token, retried = false) {
  const { auth, ...requestOptions } = options
  const headers = new Headers(options.headers)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (auth && token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...requestOptions,
    headers,
  })

  if (
    response.status === 401 &&
    auth &&
    !retried &&
    path !== '/auth/refresh'
  ) {
    const refreshToken = localStorage.getItem('kahvecell_refresh_token')
    if (refreshToken) {
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      const refreshed = await readResponse(refreshResponse)
      if (refreshResponse.ok && refreshed?.access_token) {
        saveSession(refreshed)
        notifyAuthChange()
        return sendRequest(path, options, refreshed.access_token, true)
      }
    }

    clearSession()
  }

  const data = await readResponse(response)
  if (!response.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(', ')
      : detail
    const requestError = new Error(
      message || `İstek başarısız oldu (${response.status}).`,
    )
    requestError.status = response.status
    throw requestError
  }
  return data
}

export function apiRequest(path, { method = 'GET', body, auth = true, ...rest } = {}) {
  const options = {
    ...rest,
    method,
    auth,
    body: body === undefined ? undefined : JSON.stringify(body),
  }
  const token = auth
    ? localStorage.getItem('kahvecell_access_token')
    : null
  return sendRequest(path, options, token)
}
