import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  lazy,
  Suspense,
} from 'react'
import { Alert, Button, Card, Space, message } from 'antd'
import { useQuery } from '@tanstack/react-query'
import {
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getStockKline,
  compareStrategies,
  getApiErrorMessage,
  type StrategyBacktestRequest,
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
  OptimizeResponse,
  CompareResponse,
} from '../types'
import { PageHeader } from '../components/research/ResearchPrimitives'
import { strategyKeys } from '../services/queryKeys'
import { normalizeStockCode } from '../utils/stockIdentity'
import { Link, useSearchParams } from 'react-router-dom'
import {
  mergeStrategyParameters,
  readSavedStrategyRun,
  sameStrategyRequest,
  type StrategyParameters,
} from '../utils/strategyWorkspace'
import { syncResearchHistory } from '../services/marketData'
import { STRATEGY_METADATA } from '../constants/strategy'

function Strategies() {
  const chartRef = useRef<HTMLDivElement>(null)
  const [searchParams, setSearchParams] = useSearchParams()
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
    (value) => value === null || typeof value === 'string',
  )
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)
  const [loadingOptimize, setLoadingOptimize] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const [priceSource, setPriceSource] = usePersistedState<'raw' | 'legacy'>(
    'strategies_priceSource',
    'raw',
    (value) => value === 'raw' || value === 'legacy',
  )
  const [corporateActionMode, setCorporateActionMode] = usePersistedState<
    'price_only' | 'verified'
  >(
    'strategies_corporateActionMode',
    'verified',
    (value) => value === 'price_only' || value === 'verified',
  )
  const [dividendTaxRate, setDividendTaxRate] = usePersistedState(
    'strategies_dividendTaxRate',
    0,
    (value) =>
      typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1,
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
  const [storedStock, setStoredStock] = usePersistedState<string | null>(
    'strategies_stockCode',
    null,
    (value) =>
      value === null ||
      (typeof value === 'string' && normalizeStockCode(value) !== null),
  )
  const stockCode = requestedStock ?? normalizeStockCode(storedStock)
  useEffect(() => {
    if (requestedStock) setStoredStock(requestedStock)
  }, [requestedStock, setStoredStock])
  const setStockCode = useCallback(
    (value: string | null | undefined) => {
      const code = normalizeStockCode(value)
      setStoredStock(code)
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          if (code) next.set('stock', code)
          else next.delete('stock')
          return next
        },
        { replace: true },
      )
    },
    [setStoredStock, setSearchParams],
  )
  const [dateRange, setDateRange] = usePersistedState<[string, string]>(
    'strategies_dateRange',
    [
      dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
      dayjs().subtract(1, 'day').format('YYYY-MM-DD'),
    ],
    (value) =>
      Array.isArray(value) &&
      value.length === 2 &&
      value.every(
        (date) =>
          typeof date === 'string' &&
          /^\d{4}-\d{2}-\d{2}$/.test(date) &&
          dayjs(date).isValid() &&
          dayjs(date).format('YYYY-MM-DD') === date,
      ) &&
      value[0] <= value[1],
  )
  const [initialCapital, setInitialCapital] = usePersistedState(
    'strategies_initialCapital',
    100000,
    (value) => typeof value === 'number' && Number.isFinite(value) && value > 0,
  )
  const [parameterDrafts, setParameterDrafts] = usePersistedState<
    Record<string, unknown>
  >(
    'strategies_parameterDrafts',
    {},
    (value) => value !== null && typeof value === 'object' && !Array.isArray(value),
  )
  const parameters = useMemo(
    () =>
      mergeStrategyParameters(
        strategies.find((strategy) => strategy.name === selectedStrategy),
        selectedStrategy ? parameterDrafts?.[selectedStrategy] : undefined,
      ),
    [strategies, selectedStrategy, parameterDrafts],
  )
  const setParameters = useCallback(
    (next: StrategyParameters) => {
      if (!selectedStrategy) return
      setParameterDrafts((previous) => ({ ...previous, [selectedStrategy]: next }))
    },
    [selectedStrategy, setParameterDrafts],
  )

  // Results state
  const [signals, setSignals] = useState<SignalDataPoint[]>([])
  const [signalStats, setSignalStats] = useState<SignalStats | null>(null)
  const [signalContext, setSignalContext] = useState('')
  const currentSignalContext = JSON.stringify({
    stockCode,
    dateRange,
    selectedStrategy,
    parameters,
    executionOptions,
  })
  const [storedRun, setStoredRun] = usePersistedState<unknown>(
    'strategies_savedRun',
    null,
  )
  const savedRun = useMemo(() => readSavedStrategyRun(storedRun), [storedRun])
  const backtestResult = savedRun?.result ?? null
  const [resultTab, setResultTab] = usePersistedState('strategies_resultTab', 'market')
  const activeResultTab =
    backtestResult && ['equity', 'metrics', 'trades'].includes(resultTab)
      ? resultTab
      : 'market'
  const currentRequest: StrategyBacktestRequest = {
    strategy_name: selectedStrategy ?? '',
    stock_code: stockCode ?? '',
    start_date: dateRange[0],
    end_date: dateRange[1],
    initial_capital: initialCapital,
    parameters,
    ...executionOptions,
  }
  const resultMatchesConfiguration = savedRun
    ? sameStrategyRequest(savedRun.request, currentRequest)
    : false
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResponse | null>(null)
  const chartContext = JSON.stringify([stockCode, dateRange, priceSource])
  const [researchData, setResearchData] = useState<{
    context: string
    data: KlineData[]
  } | null>(null)
  const klineData = useMemo(
    () => (researchData?.context === chartContext ? researchData.data : []),
    [researchData, chartContext],
  )

  const restoreRun = () => {
    if (!savedRun) return
    const request = savedRun.request
    setSelectedStrategy(request.strategy_name)
    setStockCode(request.stock_code)
    setDateRange([request.start_date, request.end_date])
    setInitialCapital(request.initial_capital)
    setPriceSource(request.price_source === 'legacy' ? 'legacy' : 'raw')
    setCorporateActionMode(request.corporate_action_mode ?? 'verified')
    setDividendTaxRate(request.dividend_tax_rate ?? 0)
    setParameterDrafts((previous) => ({
      ...previous,
      [request.strategy_name]: request.parameters ?? {},
    }))
  }

  // Comparison state
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)
  const [loadingCompare, setLoadingCompare] = useState(false)

  // 统一的任务轮询（超时/取消/卸载清理/指数退避）
  const { waitForJob } = useJobPolling<OptimizeResponse>({ timeoutMs: 600000 })

  const loadResearchData = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) return []
    const generation = ++chartRequest.current
    let data
    try {
      data = await getStockKline(stockCode, dateRange[0], dateRange[1], priceSource)
    } catch (error) {
      if (generation === chartRequest.current) setResearchData(null)
      throw error
    }
    if (generation === chartRequest.current)
      setResearchData({ context: chartContext, data })
    if (data.length === 0) {
      throw new Error('所选区间暂无研究行情，请先补齐研究数据')
    }
    return data
  }, [stockCode, dateRange, priceSource, chartContext])

  // Historical chart and execution use the same price source and interval.
  useEffect(() => {
    if (!stockCode) {
      setResearchData(null)
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
      setResultTab('market')
      setOptimizeResult(null)
      setSignalContext(currentSignalContext)
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
    currentSignalContext,
    setResultTab,
  ])

  const handleRunBacktest = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingBacktest(true)
    try {
      await loadResearchData()
      const request: StrategyBacktestRequest = {
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        parameters,
        ...executionOptions,
      }
      const response = await runStrategyBacktest(request)
      setStoredRun({ version: 1, request, result: response })
      setResultTab('metrics')
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
    setStoredRun,
    setResultTab,
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
    setParameters,
  ])

  const handleCompare = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和日期范围')
      return
    }
    setLoadingCompare(true)
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
    () =>
      getChartOption(
        klineData,
        signalContext === currentSignalContext ? signals : [],
        resultMatchesConfiguration ? backtestResult : null,
      ),
    [
      klineData,
      signals,
      backtestResult,
      signalContext,
      currentSignalContext,
      resultMatchesConfiguration,
    ],
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
      {backtestResult && (
        <Alert
          className="strategy-saved-context"
          type="info"
          showIcon
          message={`已保存结果 #${backtestResult.result_id} · ${backtestResult.stock_code} · ${STRATEGY_METADATA[backtestResult.strategy_name]?.name || backtestResult.strategy_name}`}
          description={`${backtestResult.start_date} — ${backtestResult.end_date}。${
            !resultMatchesConfiguration
              ? '当前配置已调整；重新执行回测后更新绩效与交易记录。'
              : '绩效与交易记录对应这次已保存运行。'
          }`}
          action={
            <Space wrap>
              <Button
                size="small"
                onClick={restoreRun}
                disabled={resultMatchesConfiguration}
              >
                恢复本次配置
              </Button>
              <Link to={`/history?result=${backtestResult.result_id}`}>查看历史</Link>
            </Space>
          }
        />
      )}

      <div className="strategies-layout">
        <div className="strategy-configuration-column">
          <details
            className="strategy-catalog-disclosure"
            open={catalogOpen || !selectedStrategy}
            onToggle={(event) => setCatalogOpen(event.currentTarget.open)}
          >
            <summary>
              {selectedStrategy
                ? `当前策略：${STRATEGY_METADATA[selectedStrategy]?.name || selectedStrategy}`
                : '选择研究策略'}
              <span>展开搜索与切换策略</span>
            </summary>
            <StrategyList
              strategies={strategies}
              selectedStrategy={selectedStrategy}
              loading={strategiesQuery.isLoading}
              onSelect={(name) => {
                setSelectedStrategy(name)
                setCatalogOpen(false)
              }}
              error={strategiesQuery.error}
              onRetry={() => void strategiesQuery.refetch()}
            />
          </details>

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
        </div>

        <StrategyResults
          activeTab={activeResultTab}
          onTabChange={setResultTab}
          klineData={klineData}
          signals={signals}
          signalStats={signalContext === currentSignalContext ? signalStats : null}
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
