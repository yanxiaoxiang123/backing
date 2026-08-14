import { describe, expect, it } from 'vitest'
import { STRATEGY_METADATA, STRATEGY_CATEGORIES } from './strategy'

// 与 backend/app/services/strategy/strategies.py 的注册名保持一致
const BACKEND_STRATEGIES = [
  'ma_cross',
  'mean_reversion',
  'momentum',
  'breakout',
  'rsi_reversal',
  'macd_cross',
  'dual_thrust',
  'turtle_trading',
  'bollinger_breakout',
  'donchian_channel',
  'aberration',
  'keltner_channel',
  'macd_divergence'
]

describe('STRATEGY_METADATA', () => {
  it('覆盖所有后端注册策略（键名一致）', () => {
    for (const name of BACKEND_STRATEGIES) {
      expect(STRATEGY_METADATA[name], `缺少元数据: ${name}`).toBeTruthy()
    }
  })

  it('名称与说明均为中文，且分类合法', () => {
    const categories = STRATEGY_CATEGORIES.map(c => c.key)
    for (const [key, meta] of Object.entries(STRATEGY_METADATA)) {
      expect(meta.name, `${key} 名称非中文`).toMatch(/[\u4e00-\u9fff]/)
      expect(meta.description, `${key} 说明非中文`).toMatch(/[\u4e00-\u9fff]/)
      expect(meta.color).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(categories, `${key} 分类非法`).toContain(meta.category)
    }
  })

  it('分类标签包含 趋势/震荡/突破/AI', () => {
    expect(STRATEGY_CATEGORIES.map(c => c.label)).toEqual(['趋势', '震荡', '突破', 'AI'])
  })
})
