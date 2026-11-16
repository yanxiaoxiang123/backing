import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  chatDraftScope,
  readChatDraft,
  writeChatDraft,
  clearChatDraft,
  moveChatDraft,
  beginChatSubmission,
  moveChatSubmission,
  endChatSubmission,
  isChatSubmitting,
} from './chatDrafts'

describe('research drafts', () => {
  beforeEach(() => sessionStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('isolates conversations and canonical stocks with thread identity taking precedence', () => {
    expect(chatDraftScope('bank', 'sh.600000')).toBe('thread:bank')
    expect(chatDraftScope(null, '600000.SH')).toBe('stock:sh.600000')
    expect(chatDraftScope(null, 'invalid')).toBe('new')
    writeChatDraft('thread:bank', '核对银行证据')
    writeChatDraft('thread:property', '核对地产风险')
    expect(readChatDraft('thread:bank')?.value).toBe('核对银行证据')
    expect(readChatDraft('thread:property')?.value).toBe('核对地产风险')
  })

  it('distinguishes deliberate empty drafts from absent data and keeps snapshots stable', () => {
    expect(readChatDraft('empty')).toBeNull()
    const saved = writeChatDraft('empty', '')
    expect(readChatDraft('empty')).toBe(saved)
    expect(readChatDraft('empty')?.value).toBe('')
    expect(readChatDraft('absent')).toBeNull()
  })

  it('ignores damaged storage without deleting unrelated data', () => {
    writeChatDraft('broken', 'before')
    const key = Object.keys(sessionStorage).find((item) => item.endsWith(':broken'))!
    sessionStorage.setItem(key, '{broken')
    sessionStorage.setItem('unrelated', 'keep')
    expect(readChatDraft('broken')).toBeNull()
    expect(sessionStorage.getItem('unrelated')).toBe('keep')
  })

  it('retains editable drafts when storage reads and writes are blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    const saved = writeChatDraft('blocked', '仍能编辑')
    expect(readChatDraft('blocked')).toBe(saved)
    expect(clearChatDraft('blocked', saved)).toBe(true)
    expect(readChatDraft('blocked')?.value).toBe('')
  })

  it('edits and conditionally clears drafts without secure-context UUID support', () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValueOnce(
      '00000000-0000-4000-8000-000000000001',
    )
    const submitted = writeChatDraft('http-origin', '原问题')
    vi.stubGlobal('crypto', {})
    try {
      const edited = writeChatDraft('http-origin', '修改后的问题')
      expect(edited.version).not.toBe(submitted.version)
      expect(readChatDraft('http-origin')?.value).toBe('修改后的问题')
      expect(clearChatDraft('http-origin', submitted)).toBe(false)
      expect(clearChatDraft('http-origin', edited)).toBe(true)
      expect(readChatDraft('http-origin')?.value).toBe('')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('never clears a newer edit, even if the user typed the same text again', () => {
    const submitted = writeChatDraft('versioned', 'same question')
    writeChatDraft('versioned', 'changed')
    writeChatDraft('versioned', 'same question')
    expect(clearChatDraft('versioned', submitted)).toBe(false)
    expect(readChatDraft('versioned')?.value).toBe('same question')
    expect(clearChatDraft('versioned', readChatDraft('versioned')!)).toBe(true)
  })

  it('moves an unchanged first draft to its created conversation', () => {
    const source = writeChatDraft('stock:sh.600000', '核验证据')
    const moved = moveChatDraft('stock:sh.600000', 'thread:created', source)
    expect(moved?.value).toBe('核验证据')
    expect(readChatDraft('stock:sh.600000')?.value).toBe('')
    expect(readChatDraft('thread:created')).toBe(moved)
  })

  it('keeps both drafts on a destination collision including deliberate empty', () => {
    const source = writeChatDraft('from', 'do not lose')
    writeChatDraft('to', '')
    expect(moveChatDraft('from', 'to', source)).toBeNull()
    expect(readChatDraft('from')).toBe(source)
    expect(readChatDraft('to')?.value).toBe('')
    writeChatDraft('from', 'newer')
    expect(moveChatDraft('from', 'absent', source)).toBeNull()
    expect(readChatDraft('absent')).toBeNull()
  })

  it('shares a submission lock through remount and created-thread handoff', () => {
    const token = beginChatSubmission('pending')!
    expect(beginChatSubmission('pending')).toBeNull()
    moveChatSubmission(token, 'thread:pending')
    expect(isChatSubmitting('pending')).toBe(true)
    expect(isChatSubmitting('thread:pending')).toBe(true)
    endChatSubmission(token)
    expect(isChatSubmitting('pending')).toBe(false)
    expect(isChatSubmitting('thread:pending')).toBe(false)
  })
})
