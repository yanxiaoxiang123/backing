import { Prose } from '../Prose'
import { ArrowRightOutlined } from '@ant-design/icons'

const prompts = [
  {
    title: '研究一只股票',
    detail: '从行情、趋势与风险入手',
    content: '帮我研究 sh.600000，先梳理趋势、成交量和主要风险，并说明判断依据。',
  },
  {
    title: '验证一个策略',
    detail: '用历史数据检验你的想法',
    content:
      '对 sh.600000 的 5 日与 20 日均线交叉策略做回测，先确认可用数据区间，再分析收益、回撤和交易成本。',
  },
  {
    title: '复核持仓风险',
    detail: '检查仓位与需要验证的假设',
    content:
      '帮我复核持仓风险。请先向我确认持仓、权重和投资期限，再检查集中度与潜在回撤。',
  },
]

export function ResearchWelcome({ onChoose }: { onChoose: (content: string) => void }) {
  return (
    <div className="research-welcome">
      <svg
        className="research-welcome-mark"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
      >
        <path d="M7 8v16m9-21v26m9-20v14" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 13h6v7H4zm9-5h6v14h-6zm9 5h6v6h-6z" fill="currentColor" />
      </svg>
      <Prose as="h2">从一个研究问题开始</Prose>
      <Prose as="p">让行情、证据与回测，沿着同一段对话展开。</Prose>
      <div className="research-prompt-list" aria-label="研究问题示例">
        {prompts.map((prompt) => (
          <button
            type="button"
            key={prompt.title}
            onClick={() => onChoose(prompt.content)}
          >
            <span>
              <strong>{prompt.title}</strong>
              <span>{prompt.detail}</span>
            </span>
            <ArrowRightOutlined aria-hidden="true" />
          </button>
        ))}
      </div>
      <span className="research-welcome-note">选择一个方向，编辑后发送。</span>
    </div>
  )
}
