async function req(method, path, body, isForm = false) {
  const opts = { method, credentials: 'include', headers: {} }
  if (body && !isForm) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  } else if (body) {
    opts.body = body
  }
  const res = await fetch(path, opts)
  if (!res.ok) {
    let detail = 'Something went wrong'
    try { detail = (await res.json()).detail || detail } catch {}
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.json()
}

async function download(path) {
  const res = await fetch(path, { credentials: 'include' })
  if (!res.ok) {
    let detail = 'Something went wrong'
    try { detail = (await res.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match?.[1] || 'deck-export'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: (p) => req('GET', p),
  post: (p, b) => req('POST', p, b),
  patch: (p, b) => req('PATCH', p, b),
  del: (p) => req('DELETE', p),
  upload: (p, formData) => req('POST', p, formData, true),
  download,
}
