// Minimal Amazon Cognito client using the public Cognito Identity Provider API.
// No SDK needed: sign-up, confirm, sign-in (USER_PASSWORD_AUTH) and token refresh.

const STORAGE_KEY = 'redactiq.session'
let cfg = null

export function initAuth(config) {
  cfg = config
}

async function cognito(action, body) {
  const res = await fetch(`https://cognito-idp.${cfg.region}.amazonaws.com/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${action}`
    },
    body: JSON.stringify(body)
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.message || data.__type || 'Authentication error')
    err.code = (data.__type || '').split('#').pop()
    throw err
  }
  return data
}

function decodeJwt(token) {
  const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
  return JSON.parse(decodeURIComponent(escape(atob(payload))))
}

function saveSession(result, email, refreshToken) {
  const session = {
    email,
    idToken: result.IdToken,
    refreshToken: result.RefreshToken || refreshToken,
    expiresAt: Date.now() + (result.ExpiresIn - 60) * 1000
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  return session
}

export function signUp(email, password) {
  return cognito('SignUp', {
    ClientId: cfg.userPoolClientId,
    Username: email,
    Password: password,
    UserAttributes: [{ Name: 'email', Value: email }]
  })
}

export function confirmSignUp(email, code) {
  return cognito('ConfirmSignUp', {
    ClientId: cfg.userPoolClientId,
    Username: email,
    ConfirmationCode: code.trim()
  })
}

export function resendCode(email) {
  return cognito('ResendConfirmationCode', { ClientId: cfg.userPoolClientId, Username: email })
}

export async function signIn(email, password) {
  const data = await cognito('InitiateAuth', {
    ClientId: cfg.userPoolClientId,
    AuthFlow: 'USER_PASSWORD_AUTH',
    AuthParameters: { USERNAME: email, PASSWORD: password }
  })
  if (!data.AuthenticationResult) {
    throw new Error(`Additional challenge required: ${data.ChallengeName}`)
  }
  return saveSession(data.AuthenticationResult, email)
}

export function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY))
  } catch {
    return null
  }
}

export function signOut() {
  sessionStorage.removeItem(STORAGE_KEY)
}

// Returns a valid ID token, refreshing it if expired.
export async function getIdToken() {
  const s = getSession()
  if (!s) throw new Error('Not signed in')
  if (Date.now() < s.expiresAt) return s.idToken
  const data = await cognito('InitiateAuth', {
    ClientId: cfg.userPoolClientId,
    AuthFlow: 'REFRESH_TOKEN_AUTH',
    AuthParameters: { REFRESH_TOKEN: s.refreshToken }
  })
  return saveSession(data.AuthenticationResult, s.email, s.refreshToken).idToken
}

export function currentUserEmail() {
  const s = getSession()
  if (!s) return null
  try {
    return decodeJwt(s.idToken).email || s.email
  } catch {
    return s.email
  }
}
