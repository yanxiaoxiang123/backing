export interface PortfolioResearchRequest {
  name: string
  weights: Record<string, number>
  start_date: string
  end_date: string
  initial_capital: number
  rebalance: 'none' | 'daily' | 'weekly' | 'monthly'
  benchmark?: string
  corporate_action_mode: 'verified' | 'price_only'
  dividend_tax_rate: number
  costs: {
    commission_rate: number
    minimum_commission: number
    sell_tax_rate: number
    transfer_rate: number
    slippage_rate: number
    max_participation: number
    lot_size: number
  }
}

export interface PortfolioPoint {
  date: string
  total_value: number
  cash: number
  receivable: number
  positions: Record<string, { quantity: number; pending_shares: number; close: number }>
}

export interface PortfolioResearchResult {
  initial_capital: number
  final_capital: number
  engine_version: string
  metrics: Record<string, number>
  portfolio_values: PortfolioPoint[]
  trades: Array<{
    date: string
    stock_code: string
    action: 'buy' | 'sell'
    quantity: number
    price: number
    fees: number
  }>
  unfilled_orders: Array<{
    date: string
    stock_code: string
    side: 'buy' | 'sell'
    quantity: number
    reason: string
  }>
  benchmark?: { stock_code: string; portfolio_values: PortfolioPoint[] }
  comparison?: {
    benchmark_return: number
    excess_return: number
    information_ratio: number
    tracking_error: number
  }
  limitations: string[]
}

export interface PortfolioExperimentSummary {
  experiment_id: string
  name: string
  created_at: string
  snapshot_sha256: string
  request: PortfolioResearchRequest
  metrics: Record<string, number>
}

export interface PortfolioExperiment extends PortfolioExperimentSummary {
  result: PortfolioResearchResult
}
