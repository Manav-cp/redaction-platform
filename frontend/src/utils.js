export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  })
}

export const ALLOWED_EXT = ['.pdf', '.txt']
export const MAX_MB = 10

export function validateFile(file) {
  const name = (file?.name || '').toLowerCase()
  if (!ALLOWED_EXT.some((ext) => name.endsWith(ext))) return 'Only PDF and TXT files are supported.'
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_MB * 1024 * 1024) return `Files must be ${MAX_MB} MB or smaller.`
  return null
}

export const PII_LABELS = {
  EMAIL: 'Email', PHONE: 'Phone', SSN: 'SSN', CREDIT_CARD: 'Card no.',
  CREDIT_DEBIT_NUMBER: 'Card no.', AADHAAR: 'Aadhaar', IN_AADHAAR: 'Aadhaar',
  PAN: 'PAN', IN_PERMANENT_ACCOUNT_NUMBER: 'PAN', IP_ADDRESS: 'IP address',
  DATE_OF_BIRTH: 'Date of birth', NAME: 'Name', ADDRESS: 'Address',
  BANK_ACCOUNT_NUMBER: 'Bank account', PASSPORT_NUMBER: 'Passport'
}

export function piiLabel(type) {
  return PII_LABELS[type] || type.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
}

export function isActive(status) {
  return status === 'PENDING_UPLOAD' || status === 'PROCESSING'
}
