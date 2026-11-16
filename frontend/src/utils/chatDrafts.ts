import { normalizeStockCode } from './stockIdentity'

export interface ChatDraft {
  value: string
  version: string
}

const PREFIX = 'backing.chat-draft:'
const cache = new Map<string, { raw: string | null; draft: ChatDraft | null }>()
const memory = new Map<string, ChatDraft>()
const listeners = new Set<() => void>()
type Submission = Set<string>
const submissions = new Map<string, Submission>()

function notify() {
  listeners.forEach((listener) => listener())
}

export function subscribeChatDrafts(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function chatDraftScope(
  threadId?: string | null,
  stockCode?: string | null,
): string {
  if (threadId) return `thread:${threadId}`
  const stock = normalizeStockCode(stockCode)
  return stock ? `stock:${stock}` : 'new'
}

export function readChatDraft(scope: string): ChatDraft | null {
  if (memory.has(scope)) return memory.get(scope)!
  let raw: string | null
  try {
    raw = window.sessionStorage.getItem(`${PREFIX}${scope}`)
  } catch {
    return cache.get(scope)?.draft ?? null
  }
  const previous = cache.get(scope)
  if (previous?.raw === raw) return previous.draft
  let draft: ChatDraft | null = null
  try {
    const parsed = raw ? JSON.parse(raw) : null
    if (typeof parsed?.value === 'string' && typeof parsed?.version === 'string')
      draft = { value: parsed.value, version: parsed.version }
  } catch {
    // A damaged draft must not prevent research or touch unrelated storage.
  }
  cache.set(scope, { raw, draft })
  return draft
}

let revision = 0

export function writeChatDraft(scope: string, value: string): ChatDraft {
  const version =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${++revision}-${Math.random().toString(36).slice(2)}`
  const draft = { value, version }
  const raw = JSON.stringify(draft)
  cache.set(scope, { raw, draft })
  try {
    window.sessionStorage.setItem(`${PREFIX}${scope}`, raw)
    memory.delete(scope)
  } catch {
    memory.set(scope, draft)
  }
  notify()
  return draft
}

export function clearChatDraft(scope: string, expected: ChatDraft): boolean {
  if (readChatDraft(scope)?.version !== expected.version) return false
  writeChatDraft(scope, '')
  return true
}

export function moveChatDraft(
  source: string,
  target: string,
  expected: ChatDraft,
): ChatDraft | null {
  if (readChatDraft(source)?.version !== expected.version) return null
  if (source === target) return expected
  if (readChatDraft(target) !== null) return null
  const moved = writeChatDraft(target, expected.value)
  clearChatDraft(source, expected)
  return moved
}

export function isChatSubmitting(scope: string): boolean {
  return submissions.has(scope)
}

export function beginChatSubmission(scope: string): Submission | null {
  if (submissions.has(scope)) return null
  const token = new Set([scope])
  submissions.set(scope, token)
  notify()
  return token
}

export function moveChatSubmission(token: Submission, scope: string): void {
  if (submissions.has(scope)) return
  token.add(scope)
  submissions.set(scope, token)
  notify()
}

export function endChatSubmission(token: Submission): void {
  for (const scope of token) {
    if (submissions.get(scope) === token) submissions.delete(scope)
  }
  notify()
}
