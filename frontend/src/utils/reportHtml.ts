import type { AgentAnalyzeResponse } from '../types'
import { escapeHtml, safeHttpUrl } from './safeHtml'

const STAGE_LABELS: Record<string, string> = {
  technical_analysis: '技术分析',
  intel: '情报分析',
  risk: '风险评估',
  strategy: '策略评估',
  decision: '决策',
}

const SIGNAL_COLORS = {
  buy: '#52c41a',
  sell: '#ff4d4f',
  hold: '#8c8c8c',
} as const

function signalLabel(signal: string): string {
  return signal === 'buy' ? '买入' : signal === 'sell' ? '卖出' : '持有'
}

function signalColor(signal: string): string {
  return SIGNAL_COLORS[signal as keyof typeof SIGNAL_COLORS] ?? SIGNAL_COLORS.hold
}

function safeNumber(value: unknown, digits = 1): string {
  const number = typeof value === 'number' && Number.isFinite(value) ? value : 0
  return number.toFixed(digits)
}

/**
 * Build a standalone, print-friendly report from a typed API response.
 * Every model-controlled string is escaped before entering the HTML document;
 * external links are restricted to HTTP(S) URLs.
 */
export function buildAgentReportHtml(report: AgentAnalyzeResponse): string {
  const stageRows = report.stages
    .map((stage) => {
      const name = escapeHtml(STAGE_LABELS[stage.stage_name] || stage.stage_name)
      if (stage.opinion) {
        const color = signalColor(stage.opinion.signal)
        return `<tr>
          <td class="cell cell--strong">${name}</td>
          <td class="cell"><span class="signal" style="color:${color}">${signalLabel(stage.opinion.signal)}</span></td>
          <td class="cell">${Math.round(stage.opinion.confidence * 100)}%</td>
          <td class="cell">${escapeHtml(stage.opinion.reason || '—')}</td>
        </tr>`
      }
      return `<tr>
        <td class="cell cell--strong">${name}</td>
        <td colspan="3" class="cell cell--muted">${escapeHtml(stage.error || '无结果')}</td>
      </tr>`
    })
    .join('')

  const newsSection = report.news_items?.length
    ? `<h2>相关新闻</h2>
         <ul class="news-list">
           ${report.news_items
             .map((item) => {
               const href = safeHttpUrl(item.url)
               const title = escapeHtml(item.title || '新闻')
               const content = escapeHtml(
                 item.content ? item.content.slice(0, 200) : '',
               )
               const link = href
                 ? `<a href="${escapeHtml(href)}" rel="noopener noreferrer">${title}</a>`
                 : title
               return `<li>${link}<br/><span class="news-content">${content}</span></li>`
             })
             .join('')}
         </ul>`
    : ''

  const color = signalColor(report.final_signal)
  const arrow =
    report.final_signal === 'buy' ? '↑' : report.final_signal === 'sell' ? '↓' : '→'

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI Agent 分析报告 - ${escapeHtml(report.stock_code)}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; color: #222; line-height: 1.6; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 16px; margin: 24px 0 12px; }
  .subtitle { color: #666; font-size: 14px; margin-bottom: 24px; }
  .signal-card { text-align: center; padding: 24px; background: #f5f5f5; border-radius: 8px; margin-bottom: 24px; }
  .signal-card .arrow { font-size: 48px; font-weight: 700; }
  .signal-card .label { font-size: 20px; font-weight: 600; margin: 8px 0 4px; }
  .signal-card .meta { font-size: 14px; color: #666; }
  .reason-box { background: #fafafa; border: 1px solid #e8e8e8; border-radius: 6px; padding: 12px 16px; margin: 16px 0; font-size: 14px; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th { background: #fafafa; padding: 8px 12px; border: 1px solid #e8e8e8; text-align: left; font-weight: 600; font-size: 13px; }
  .cell { padding: 8px 12px; border: 1px solid #e8e8e8; }
  .cell--strong { font-weight: 600; }
  .cell--muted { color: #999; }
  .signal { font-weight: 600; }
  .news-list { padding-left: 20px; }
  .news-list li { margin-bottom: 8px; }
  .news-list a { color: #1677ff; }
  .news-content { font-size: 13px; color: #666; }
  .footer { margin-top: 32px; font-size: 12px; color: #999; text-align: center; }
  @media print { body { margin: 20px; } }
</style>
</head>
<body>
  <h1>AI Agent 分析报告</h1>
  <div class="subtitle">${escapeHtml(report.stock_name)} (${escapeHtml(report.stock_code)}) | ${escapeHtml(report.mode)}模式 | ${safeNumber(report.duration_s)}s</div>
  <div class="signal-card">
    <div class="arrow" style="color:${color}">${arrow}</div>
    <div class="label" style="color:${color}">${signalLabel(report.final_signal)}</div>
    <div class="meta">置信度: ${Math.round(report.final_confidence * 100)}%</div>
  </div>
  <h2>结论</h2>
  <div class="reason-box">${escapeHtml(report.final_reason || '无')}</div>
  <h2>各阶段详情</h2>
  <table>
    <thead><tr><th style="width:22%">阶段</th><th style="width:10%">信号</th><th style="width:10%">置信度</th><th>分析理由</th></tr></thead>
    <tbody>${stageRows}</tbody>
  </table>
  ${newsSection}
  <p class="footer">由 Backing AI Agent 系统生成</p>
</body>
</html>`
}
