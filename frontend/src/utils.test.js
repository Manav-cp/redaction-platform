import { describe, expect, it } from 'vitest'
import { formatBytes, isActive, piiLabel, validateFile } from './utils.js'

describe('utils', () => {
  it('formats bytes', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('validates file type and size', () => {
    expect(validateFile({ name: 'a.pdf', size: 100 })).toBeNull()
    expect(validateFile({ name: 'a.TXT', size: 100 })).toBeNull()
    expect(validateFile({ name: 'a.exe', size: 100 })).toMatch(/Only PDF/)
    expect(validateFile({ name: 'a.pdf', size: 0 })).toMatch(/empty/)
    expect(validateFile({ name: 'a.pdf', size: 20 * 1024 * 1024 })).toMatch(/10 MB/)
  })

  it('labels PII types', () => {
    expect(piiLabel('EMAIL')).toBe('Email')
    expect(piiLabel('SWIFT_CODE')).toBe('Swift code')
  })

  it('detects active statuses', () => {
    expect(isActive('PROCESSING')).toBe(true)
    expect(isActive('COMPLETED')).toBe(false)
  })
})
