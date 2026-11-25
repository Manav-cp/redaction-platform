import React, { useCallback, useEffect, useRef, useState } from 'react'
import { deleteDocument, getDocument, listDocuments, uploadFile } from './api.js'
import { confirmSignUp, currentUserEmail, getSession, resendCode, signIn, signOut, signUp } from './auth.js'
import { formatBytes, formatDate, isActive, piiLabel, validateFile } from './utils.js'

export default function App() {
  const [signedIn, setSignedIn] = useState(!!getSession())
  return signedIn
    ? <Dashboard onSignOut={() => { signOut(); setSignedIn(false) }} />
    : <AuthView onSignedIn={() => setSignedIn(true)} />
}

/* ------------------------------------------------------------------ Auth */
function AuthView({ onSignedIn }) {
  const [mode, setMode] = useState('signin') // signin | signup | confirm
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(''); setInfo('')
    try {
      if (mode === 'signin') {
        await signIn(email, password)
        onSignedIn()
      } else if (mode === 'signup') {
        await signUp(email, password)
        setMode('confirm')
        setInfo(`We emailed a 6-digit verification code to ${email}.`)
      } else {
        await confirmSignUp(email, code)
        await signIn(email, password)
        onSignedIn()
      }
    } catch (err) {
      if (err.code === 'UserNotConfirmedException') {
        setMode('confirm')
        setInfo('Your account is not verified yet. Enter the code we emailed you.')
      } else {
        setError(err.message)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <Logo />
        <h1>Strip sensitive data from documents before they travel.</h1>
        <p>Upload invoices, contracts or résumés. A serverless pipeline finds emails, phone numbers,
          card numbers, Aadhaar, PAN, and returns a clean copy in seconds.</p>
        <ul className="hero-points">
          <li>Data encryption — TLS in transit, AES-256 at rest</li>
          <li>Private document storage on Amazon S3</li>
          <li>Regex-based sensitive data detection</li>
        </ul>
      </section>

      <form className="auth-card" onSubmit={submit}>
        <h2>{mode === 'signin' ? 'Sign in' : mode === 'signup' ? 'Create account' : 'Verify email'}</h2>
        {info && <p className="note">{info}</p>}
        <label>Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} disabled={mode === 'confirm'} autoComplete="email" />
        </label>
        {mode !== 'confirm' && (
          <label>Password
            <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
            {mode === 'signup' && <small>At least 8 characters with upper case, lower case and a number.</small>}
          </label>
        )}
        {mode === 'confirm' && (
          <>
            <label>Verification code
              <input inputMode="numeric" required value={code} onChange={(e) => setCode(e.target.value)} />
            </label>
            {!password && (
              <label>Password
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </label>
            )}
          </>
        )}
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : mode === 'signup' ? 'Create account' : 'Verify and sign in'}
        </button>
        <div className="auth-switch">
          {mode === 'signin' && <>New here? <button type="button" className="link" onClick={() => { setMode('signup'); setError('') }}>Create an account</button></>}
          {mode === 'signup' && <>Already registered? <button type="button" className="link" onClick={() => { setMode('signin'); setError('') }}>Sign in</button></>}
          {mode === 'confirm' && <button type="button" className="link" onClick={() => resendCode(email).then(() => setInfo('A new code is on its way.')).catch((e) => setError(e.message))}>Resend code</button>}
        </div>
      </form>
    </div>
  )
}

/* ------------------------------------------------------------- Dashboard */
function Dashboard({ onSignOut }) {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploads, setUploads] = useState({}) // name -> progress
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocuments())
      setError('')
    } catch (e) {
      if (e.status === 401) onSignOut()
      else setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [onSignOut])

  useEffect(() => { refresh() }, [refresh])

  // Poll while anything is still processing
  useEffect(() => {
    if (!docs.some((d) => isActive(d.status))) return
    const t = setInterval(refresh, 2500)
    return () => clearInterval(t)
  }, [docs, refresh])

  async function handleFiles(fileList) {
    for (const file of Array.from(fileList)) {
      const problem = validateFile(file)
      if (problem) { setError(`${file.name}: ${problem}`); continue }
      setUploads((u) => ({ ...u, [file.name]: 0 }))
      try {
        await uploadFile(file, (p) => setUploads((u) => ({ ...u, [file.name]: p })))
      } catch (e) {
        setError(`${file.name}: ${e.message}`)
      } finally {
        setUploads((u) => { const n = { ...u }; delete n[file.name]; return n })
        refresh()
      }
    }
  }

  async function download(doc) {
    try {
      const fresh = await getDocument(doc.docId)
      if (fresh.downloadUrl) window.location.assign(fresh.downloadUrl)
    } catch (e) { setError(e.message) }
  }

  async function remove(doc) {
    if (!window.confirm(`Delete ${doc.fileName} and its redacted copy?`)) return
    try { await deleteDocument(doc.docId); refresh() } catch (e) { setError(e.message) }
  }

  const totalPii = docs.reduce((s, d) => s + (d.piiTotal || 0), 0)
  const completed = docs.filter((d) => d.status === 'COMPLETED').length

  return (
    <div className="app">
      <header className="topbar">
        <Logo />
        <div className="user">
          <span>{currentUserEmail()}</span>
          <button className="ghost" onClick={onSignOut}>Sign out</button>
        </div>
      </header>

      <main>
        <section className="stats">
          <Stat label="Documents" value={docs.length} />
          <Stat label="Redacted" value={completed} />
          <Stat label="PII items removed" value={totalPii} accent />
        </section>

        <section
          className={`dropzone ${dragging ? 'dragging' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => inputRef.current?.click()}
          role="button" tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" accept=".pdf,.txt" multiple hidden onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }} />
          <div className="drop-icon" aria-hidden>⇪</div>
          <strong>Drop PDF or TXT files here, or click to browse</strong>
          <span>Up to 10 MB each. Files go straight to an encrypted S3 bucket via a 5-minute pre-signed link.</span>
          {Object.entries(uploads).map(([name, p]) => (
            <div className="progress" key={name}><span>{name}</span><div><i style={{ width: `${p}%` }} /></div></div>
          ))}
        </section>

        {error && <div className="banner-error" onClick={() => setError('')}>{error} <span>✕</span></div>}

        <section className="docs">
          <div className="docs-head">
            <h2>Your documents</h2>
            <button className="ghost" onClick={refresh}>Refresh</button>
          </div>
          {loading ? <p className="muted">Loading…</p>
            : docs.length === 0 ? <p className="muted empty">No documents yet. Try one of the samples in the <code>samples/</code> folder.</p>
              : (
                <table>
                  <thead><tr><th>File</th><th>Uploaded</th><th>Status</th><th>Findings</th><th /></tr></thead>
                  <tbody>
                    {docs.map((d) => (
                      <tr key={d.docId}>
                        <td><div className="fname">{d.fileName}</div><small className="muted">{formatBytes(d.sizeBytes)}</small></td>
                        <td>{formatDate(d.createdAt)}</td>
                        <td><StatusPill status={d.status} title={d.errorMessage} /></td>
                        <td className="findings">
                          {d.piiCounts && Object.keys(d.piiCounts).length > 0
                            ? Object.entries(d.piiCounts).map(([k, v]) => <span className="chip" key={k}>{piiLabel(k)} × {v}</span>)
                            : d.status === 'COMPLETED' ? <span className="muted">None found</span>
                              : d.status === 'FAILED' ? <span className="error-text">{d.errorMessage}</span> : '—'}
                          {d.engine && <small className="muted engine">{d.engine} · {d.processingMs} ms</small>}
                        </td>
                        <td className="actions">
                          <div>
                            <button className="primary small" disabled={d.status !== 'COMPLETED'} onClick={() => download(d)}>Download</button>
                            <button className="ghost small" onClick={() => remove(d)} aria-label="Delete">Delete</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
        </section>
      </main>
      <footer>AWS Serverless Backend | S3 | Lambda | DynamoDB | Cognito | API Gateway | React</footer>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return <div className={`stat ${accent ? 'accent' : ''}`}><span>{label}</span><strong>{value}</strong></div>
}

function StatusPill({ status, title }) {
  const text = { PENDING_UPLOAD: 'Uploading', PROCESSING: 'Processing', COMPLETED: 'Redacted', FAILED: 'Failed' }[status] || status
  return <span className={`pill ${status?.toLowerCase()}`} title={title || ''}>{text}</span>
}

function Logo() {
  return (
    <div className="logo">
      <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden>
        <rect width="32" height="32" rx="7" fill="currentColor" />
        <rect x="7" y="9" width="18" height="3" fill="#fff" />
        <rect x="7" y="15" width="12" height="3" fill="#f2b134" />
        <rect x="7" y="21" width="15" height="3" fill="#fff" />
      </svg>
      <span>Redact<b>IQ</b></span>
    </div>
  )
}


