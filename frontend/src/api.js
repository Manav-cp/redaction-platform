import { getIdToken } from './auth.js'

let apiUrl = ''

export function initApi(config) {
  apiUrl = config.apiUrl.replace(/\/$/, '')
}

async function request(method, path, body) {
  const token = await getIdToken()
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.message || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

export const listDocuments = () => request('GET', '/documents').then((d) => d.documents)
export const getDocument = (id) => request('GET', `/documents/${encodeURIComponent(id)}`)
export const deleteDocument = (id) => request('DELETE', `/documents/${encodeURIComponent(id)}`)

// 1) ask API for a pre-signed POST, 2) upload the file straight to S3
export async function uploadFile(file, onProgress) {
  const { docId, upload } = await request('POST', '/upload-url', {
    fileName: file.name,
    size: file.size
  })
  const form = new FormData()
  Object.entries(upload.fields).forEach(([k, v]) => form.append(k, v))
  form.append('file', file) // must be the last field

  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', upload.url)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100))
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 upload failed (${xhr.status})`)))
    xhr.onerror = () => reject(new Error('Network error during upload'))
    xhr.send(form)
  })
  return docId
}
