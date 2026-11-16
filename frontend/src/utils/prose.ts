/** Keep the final two Han characters and punctuation together without changing text. */
export function splitProseTail(text: string): [string, string] {
  if (/https?:\/\/|www\./iu.test(text)) return [text, '']
  const tail = text.match(/[\p{Script=Han}]{2}[\p{P}]*\s*$/u)
  return tail && text.trim().length > 2
    ? [text.slice(0, -tail[0].length), tail[0]]
    : [text, '']
}
