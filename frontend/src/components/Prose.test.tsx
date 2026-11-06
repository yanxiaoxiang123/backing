import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Prose } from './Prose'
import { splitProseTail } from '../utils/prose'

describe('Chinese prose wrapping', () => {
  it('keeps the final Han pair with punctuation without changing the content', () => {
    const text = '先核对样本覆盖范围，再评估风险。'
    render(<Prose as="h2">{text}</Prose>)
    expect(screen.getByRole('heading', { name: text })).toHaveTextContent(text)
    expect(document.querySelector('.prose-tail')).toHaveTextContent('风险。')
  })

  it('preserves inline formatting, focus refs and non-prose values', () => {
    const ref = createRef<HTMLHeadingElement>()
    render(
      <Prose as="h2" ref={ref} tabIndex={-1}>
        预测窗口 <strong>请核对交易日期。</strong>
      </Prose>,
    )
    ref.current?.focus()
    expect(screen.getByRole('heading')).toHaveFocus()
    expect(document.querySelector('strong .prose-tail')).toHaveTextContent('日期。')
    for (const text of ['12.30', '2026-11-05', 'sh.600000', 'https://example.com/中文'])
      expect(splitProseTail(text)).toEqual([text, ''])
  })
})
