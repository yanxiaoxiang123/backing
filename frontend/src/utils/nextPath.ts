/**
 * 只允许站内绝对路径作为登录后的回跳目标。
 * 拒绝协议相对地址（//evil.com）、反斜杠变体（/\evil.com）和外部 URL。
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (!value) return null
  if (!value.startsWith('/')) return null
  if (value.startsWith('//')) return null
  if (value.startsWith('/\\')) return null
  return value
}
