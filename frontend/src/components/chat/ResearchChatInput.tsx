import { useEffect, useRef, useSyncExternalStore } from 'react'
import { ChatInput } from './ChatInput'
import type { ChatSendResult } from '../../hooks/useAgentChat'
import {
  beginChatSubmission,
  chatDraftScope,
  clearChatDraft,
  endChatSubmission,
  isChatSubmitting,
  moveChatDraft,
  moveChatSubmission,
  readChatDraft,
  subscribeChatDrafts,
  writeChatDraft,
} from '../../utils/chatDrafts'

interface ResearchChatInputProps {
  threadId?: string | null
  stockCode?: string | null
  running: boolean
  disabled?: boolean
  sendDisabled?: boolean
  initialValue?: string
  draft?: { value: string; revision: number }
  onSend: (
    content: string,
    onThreadCreated: (threadId: string) => void,
  ) => Promise<ChatSendResult>
  onStop: () => void
}

export function ResearchChatInput({
  threadId,
  stockCode,
  initialValue = '',
  draft,
  onSend,
  ...inputProps
}: ResearchChatInputProps) {
  const scope = chatDraftScope(threadId, stockCode)
  const stored = useSyncExternalStore(
    subscribeChatDrafts,
    () => readChatDraft(scope),
    () => null,
  )
  const submitting = useSyncExternalStore(
    subscribeChatDrafts,
    () => isChatSubmitting(scope),
    () => false,
  )
  const value = stored?.value ?? initialValue
  const appliedWelcome = useRef<typeof draft>()

  useEffect(() => {
    if (initialValue && readChatDraft(scope) === null)
      writeChatDraft(scope, initialValue)
  }, [scope, initialValue])

  useEffect(() => {
    if (!draft || appliedWelcome.current === draft) return
    appliedWelcome.current = draft
    writeChatDraft(scope, draft.value)
  }, [draft, scope])

  const send = async (content: string): Promise<boolean> => {
    const token = beginChatSubmission(scope)
    if (!token) return false
    try {
      let submitted = {
        scope,
        snapshot: readChatDraft(scope) ?? writeChatDraft(scope, value),
      }
      const result = await onSend(content, (createdId) => {
        const target = chatDraftScope(createdId)
        moveChatSubmission(token, target)
        const moved = moveChatDraft(submitted.scope, target, submitted.snapshot)
        if (moved) submitted = { scope: target, snapshot: moved }
      })
      if (result.accepted) clearChatDraft(submitted.scope, submitted.snapshot)
      return result.accepted
    } finally {
      endChatSubmission(token)
    }
  }

  return (
    <ChatInput
      key={scope}
      {...inputProps}
      value={value}
      onChange={(next) => writeChatDraft(scope, next)}
      draft={draft}
      submitting={submitting}
      onSend={send}
    />
  )
}
