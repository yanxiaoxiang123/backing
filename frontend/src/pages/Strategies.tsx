import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  lazy,
  Suspense,
} from 'react'
import { Card, message } from 'antd'
import { useQuery } from '@tanstack/react-query'
import {
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getStockKline,
  compareStrategies,
  getApiErrorMessage,
} from '../services/api'
import { getStrategies } from '../services/strategies'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import { useJobPolling } from '../hooks/useJobPolling'
import { getChartOption, getPortfolioChartOption, KlineData } from '../utils/chart'
import { buildOptimizationGrid } from '../utils/optimization'
import dayjs from 'dayjs'
import { StrategyList } from '../components/strategies/StrategyList'
import { StrategyConfig } from '../components/strategies/StrategyConfig'
import { StrategyResults } from '../components/strategies/StrategyResults'
const BacktestDetails = lazy(
  () => import('../components/strategies/details/BacktestDetails'),
)
import type {
  StrategyInfo,
  SignalDataPoint,
  SignalStats,
  StrategyBacktestResponse,
  OptimizeResponse,
  CompareResponse,
} from '../types'
import { PageHeader } from '../components/research/ResearchPrimitives'
import { strategyKeys } from '../services/queryKeys'
import { normalizeStockCode } from '../utils/stockIdentity'
import { useSearchParams } from 'react-router-dom'
import { syncResearchHistory } from '../services/marketData'

function Strategies() {
  const chartRef = useRef<HTMLDivElement>(null)
  const [searchParams] = useSearchParams()
  const requestedStock = normalizeStockCode(searchParams.get('stock'))

  // State
  const strategiesQuery = useQuery({
    queryKey: strategyKeys.catalog(),
    queryFn: getStrategies,
    staleTime: 5 * 60_000,
  })
  const strategies = useMemo<StrategyInfo[]>(
    () => strategiesQuery.data ?? [],
    [strategiesQuery.data],
  )
  const [selectedStrategy, setSelectedStrategy] = usePersistedState<string | null>(
    'strategies_selectedStrategy',
    null,
  )
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)
  const [loadingOptimize, setLoadingOptimize] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const [priceSource, setPriceSource] = usePersistedState<'raw' | 'legacy'>(
    'strategies_priceSource',
    'raw',
  )
  const [corporateActionMode, setCorporateActionMode] = usePersistedState<
    'price_only' | 'verified'
  >('strategies_corporateActionMode', 'verified')
  const [dividendTaxRate, setDividendTaxRate] = usePersistedState(
    'strategies_dividendTaxRate',
    0,
  )
  const executionOptions = useMemo(
    () => ({
      price_source: priceSource,
      corporate_action_mode:
        priceSource === 'legacy' ? ('price_only' as const) : corporateActionMode,
      dividend_tax_rate: dividendTaxRate,
    }),
    [priceSource, corporateActionMode, dividendTaxRate],
  )
  const chartRequest = useRef(0)

  // Form state
  const [stockCode, setStockCode] = usePersistedState<string | null>(
    'strategies_stockCode',
    null,
  )

  useEffect(() => {
    if (requestedStock && requestedStock !== stockCode) setStockCode(requestedStock)
  }, [requestedStock, setStockCode, stockCode])
  const [dateRange, setDateRange] = usePersistedState<[string, string]>(
    'strategies_dateRange',
    [
      dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
      dayjs().subtract(1, 'day').format('YYYY-MM-DD'),
    ],
  )
  const [initialCapital, setInitialCapital] = usePersistedState(
    'strategies_initialCapital',
    100000,
  )
  const [parameters, setParameters] = useState<Record<string, number | string>>({})

  // Results state
  const [signals, setSignals] = useState<SignalDataPoint[]>([])
  const [signalStats, setSignalStats] = useState<SignalStats | null>(null)
  const [backtestResult, setBacktestResult] = useState<StrategyBacktestResponse | null>(
    null,
  )
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResponse | null>(null)
  const [klineData, setKlineData] = useState<KlineData[]>([])

  // Comparison state
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)
  const [loadingCompare, setLoadingCompare] = useState(false)

  // 统一的任务轮询（超时/取消/卸载清理/指数退避）
  const { waitForJob } = useJobPolling<OptimizeResponse>({ timeoutMs: 600000 })

  // Update parameters when strategy changes
  useEffect(() => {
    if (selectedStrategy && strategies.length > 0) {
      const strategy = strategies.find((s) => s.name === selectedStrategy)
      if (strategy) {
        const defaultParams: Record<string, number | string> = {}
        Object.entries(strategy.parameters).forEach(([key, config]) => {
          defaultParams[key] = config.default
        })
        setParameters(defaultParams)
      }
    }
  }, [selectedStrategy, strategies])

  const loadResearchData = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) return []
    const generation = ++chartRequest.current
    let data
    try {
      data = await getStockKline(stockCode, dateRange[0], dateRange[1], priceSource)
    } catch (error) {
      if (generation === chartRequest.current) setKlineData([])
      throw error
    }
    if (generation === chartRequest.current) setKlineData(data)
    if (data.length === 0) {
      throw new Error('所选区间暂无研究行情，请先补齐研究数据')
    }
    return data
  }, [stockCode, dateRange, priceSource])

  // Historical chart and execution use the same price source and interval.
  useEffect(() => {
    if (!stockCode) {
      setKlineData([])
      return
    }
    loadResearchData().catch((error) => {
      logger.error(error)
    })
    return () => {
      chartRequest.current += 1
    }
  }, [stockCode, dateRange, loadResearchData])

  const handleSyncData = useCallback(async () => {
    if (!stockCode) return
    setLoadingData(true)
    try {
      const jobId = await syncResearchHistory(stockCode, dateRange[0], dateRange[1])
      await waitForJob(jobId)
      await loadResearchData()
      message.success('原始行情、停牌状态及分红复权数据已补齐')
    } catch (error) {
      message.error(getApiErrorMessage(error))
    } finally {
      setLoadingData(false)
    }
  }, [stockCode, dateRange, waitForJob, loadResearchData])

  const handleGenerateSignals = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingSignals(true)
    setBacktestResult(null)
    setOptimizeResult(null)
    try {
      await loadResearchData()
      const response = await generateSignals({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        parameters,
        ...executionOptions,
      })
      setSignals(response.data)
      setSignalStats(response.stats ?? null)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingSignals(false)
    }
  }, [
    selectedStrategy,
    stockCode,
    dateRange,
    parameters,
    loadResearchData,
    executionOptions,
  ])

  const handleRunBacktest = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingBacktest(true)
    try {
      await loadResearchData()
      const response = await runStrategyBacktest({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        parameters,
        ...executionOptions,
      })
      setBacktestResult(response)
      setSignals([])
      message.success(`回测已保存，历史记录 #${response.result_id}`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingBacktest(false)
    }
  }, [
    selectedStrategy,
    stockCode,
    dateRange,
    initialCapital,
    parameters,
    loadResearchData,
    executionOptions,
  ])

  const handleOptimize = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingOptimize(true)
    try {
      await loadResearchData()
      const strategy = strategies.find((s) => s.name === selectedStrategy)
      if (!strategy) return

      const includedNames =
        selectedStrategy === 'lstm_5d'
          ? new Set(['buy_threshold', 'sell_threshold', 'min_confidence'])
          : undefined
      const paramGrid = buildOptimizationGrid(strategy, 200, includedNames)

      if (Object.keys(paramGrid).length === 0) {
        message.warning('当前策略无可优化参数')
        return
      }

      const submission = await submitOptimizeParameters({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        param_grid: paramGrid,
        metric: 'sharpe_ratio',
        ...executionOptions,
      })
      const response = await waitForJob(submission.job_id)
      setOptimizeResult(response)
      setParameters(response.best_params)
      message.success(`优化完成，最佳夏普比率: ${response.best_score.toFixed(4)}`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingOptimize(false)
    }
  }, [
    selectedStrategy,
    stockCode,
    dateRange,
    initialCapital,
    strategies,
    waitForJob,
    loadResearchData,
    executionOptions,
  ])

  const handleCompare = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和日期范围')
      return
    }
    setLoadingCompare(true)
    setCompareResult(null)
    try {
      await loadResearchData()
      const response = await compareStrategies({
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        ...executionOptions,
      })
      setCompareResult(response)
      message.success(`对比完成: ${response.total_strategies} 个策略`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingCompare(false)
    }
  }, [stockCode, dateRange, initialCapital, loadResearchData, executionOptions])

  const getCurrentChartOption = useMemo(
    () => getChartOption(klineData, signals, backtestResult),
    [klineData, signals, backtestResult],
  )
  const getCurrentPortfolioChartOption = useMemo(
    () => getPortfolioChartOption(backtestResult?.portfolio_values ?? []),
    [backtestResult],
  )

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="STRATEGY LAB"
        title="策略研究"
        subtitle="选择策略、配置参数并验证历史表现"
      />

      <div className="strategies-layout">
        <StrategyList
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          loading={strategiesQuery.isLoading}
          onSelect={setSelectedStrategy}
          error={strategiesQuery.error}
          onRetry={() => void strategiesQuery.refetch()}
        />

        <StrategyConfig
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          stockCode={stockCode}
          dateRange={dateRange}
          initialCapital={initialCapital}
          parameters={parameters}
          priceSource={priceSource}
          corporateActionMode={corporateActionMode}
          dividendTaxRate={dividendTaxRate}
          loadingData={loadingData}
          onPriceSourceChange={setPriceSource}
          onCorporateActionModeChange={setCorporateActionMode}
          onDividendTaxRateChange={setDividendTaxRate}
          onSyncData={handleSyncData}
          loading={{
            signals: loadingSignals,
            backtest: loadingBacktest,
            optimize: loadingOptimize,
            compare: loadingCompare,
          }}
          onStockCodeChange={setStockCode}
          onDateRangeChange={setDateRange}
          onCapitalChange={setInitialCapital}
          onParameterChange={setParameters}
          onGenerateSignals={handleGenerateSignals}
          onRunBacktest={handleRunBacktest}
          onOptimize={handleOptimize}
          onCompare={handleCompare}
        />

        <StrategyResults
          klineData={klineData}
          signals={signals}
          signalStats={signalStats}
          backtestResult={backtestResult}
          loading={{ signals: loadingSignals, backtest: loadingBacktest }}
          chartRef={chartRef}
          chartOption={getCurrentChartOption}
          portfolioChartOption={getCurrentPortfolioChartOption}
        >
          {Boolean(optimizeResult || compareResult) && (
            <Suspense
              fallback={<Card loading style={{ marginTop: 'var(--space-md)' }} />}
            >
              <BacktestDetails
                optimizeResult={optimizeResult}
                compareResult={compareResult}
                onRunBestBacktest={handleRunBacktest}
                onSelectStrategy={setSelectedStrategy}
              />
            </Suspense>
          )}
        </StrategyResults>
      </div>
    </div>
  )
}

export default Strategies
