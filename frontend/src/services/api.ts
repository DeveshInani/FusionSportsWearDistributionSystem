const API_BASE = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '') || '/api'

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  const endpoint = path.startsWith('/api/')
    ? path.slice('/api'.length)
    : path
  return `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers ?? {})
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(apiUrl(path), { ...options, headers })
  const text = await response.text()
  if (!response.ok) {
    let message = text || `Request failed (${response.status})`
    try {
      const body = JSON.parse(text) as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // Keep the server response when it isn't JSON.
    }
    throw new Error(message)
  }
  return text ? (JSON.parse(text) as T) : (undefined as T)
}

export async function downloadInvoice(orderId: number, token: string) {
  return downloadPdf(`/orders/${orderId}/invoice`, token, `invoice-${orderId}.pdf`)
}

export async function downloadAdminInvoice(orderId: number, token: string) {
  return downloadPdf(`/admin/orders/${orderId}/invoice`, token, `invoice-${orderId}.pdf`)
}

async function downloadPdf(path: string, token: string, filename: string) {
  const response = await fetch(apiUrl(path), {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Invoice could not be downloaded.')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
