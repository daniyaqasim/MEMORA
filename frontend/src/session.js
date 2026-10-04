const SESSION_STORAGE_KEY = 'memora_session_id'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function createSessionId() {
  if (typeof crypto?.randomUUID === 'function') return crypto.randomUUID()

  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`
}

export function getMemoraSessionId() {
  const existingSessionId = window.localStorage.getItem(SESSION_STORAGE_KEY)
  if (existingSessionId && UUID_PATTERN.test(existingSessionId)) return existingSessionId

  const sessionId = createSessionId()
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId)
  return sessionId
}

export function memoraSessionHeaders() {
  return { 'X-Memora-Session': getMemoraSessionId() }
}
