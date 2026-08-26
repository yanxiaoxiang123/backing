import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { message } from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  getStrategies,
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getRealtimeBars,
  compareStrategies,
  getApiErrorMessage,
} from '../services/api'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import { useJobPolling } from '../hooks/useJobPolling'
import { getChartOption, getPortfolioChartOption, KlineData } from '../utils/chart'
import { buildOptimizationGrid } from '../utils/optimization'
import dayjs from 'dayjs'
import { StrategyList } from '../components/strategies/StrategyList'
import { StrategyConfig } from '../components/strategies/StrategyConfig'
import { StrategyResults } from '../components/strategies/StrategyResults'
import { BacktestDetails } from '../components/strategies/details/BacktestDetails'
import type {
  StrategyInfo,
  SignalDataPoint,
  SignalStats,
  StrategyBacktestResponse,
  OptimizeResponse,
  CompareResponse,
} from '../types'

function Strategies() {
  const chartRef = useRef<ReactECharts>(null)

  // State
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [selectedStrategy, setSelectedStrategy] = usePersistedState<string | null>(
    'strategies_selectedStrategy',
    null,
  )
  const [loadingStrategies, setLoadingStrategies] = useState(true)
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [loadingBacktest, setLoadingBacktest] = useState(false)
  const [loadingOptimize, setLoadingOptimize] = useState(false)

  // Form state
  const [stockCode, setStockCode] = usePersistedState<string | null>(
    'strategies_stockCode',
    null,
  )
  const [dateRange, setDateRange] = usePersistedState<[string, string]>(
    'strategies_dateRange',
    [dayjs().subtract(1, 'year').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
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

  // Load strategies on mount
  useEffect(() => {
    loadData()
  }, [])

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

  const loadData = async () => {
    try {
      setLoadingStrategies(true)
      const strategiesData = await getStrategies()
      setStrategies(strategiesData)
    } catch (error) {
      message.error('加载数据失败')
      logger.error(error)
    } finally {
      setLoadingStrategies(false)
    }
  }

  const loadMootdxData = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) return []
    const response = await getRealtimeBars(stockCode, 'daily', true)
    const data = response.data.filter(
      (bar) => bar.date >= dateRange[0] && bar.date <= dateRange[1],
    )
    setKlineData(data)
    if (data.length === 0) {
      throw new Error('mootdx 未返回所选区间的 K 线数据')
    }
    return data
  }, [stockCode, dateRange])

  // 与股票管理页使用同一 mootdx 行情源；选股或修改区间后立即刷新图表。
  useEffect(() => {
    if (!stockCode) {
      setKlineData([])
      return
    }
    loadMootdxData().catch((error) => {
      setKlineData([])
      logger.error(error)
    })
  }, [stockCode, dateRange, loadMootdxData])

  const handleGenerateSignals = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingSignals(true)
    setBacktestResult(null)
    setOptimizeResult(null)
    try {
      await loadMootdxData()
      const response = await generateSignals({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        parameters,
      })
      setSignals(response.data)
      setSignalStats(response.stats ?? null)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingSignals(false)
    }
  }, [selectedStrategy, stockCode, dateRange, parameters, loadMootdxData])

  const handleRunBacktest = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingBacktest(true)
    try {
      await loadMootdxData()
      const response = await runStrategyBacktest({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
        parameters,
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
    loadMootdxData,
  ])

  const handleOptimize = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingOptimize(true)
    try {
      await loadMootdxData()
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
    loadMootdxData,
  ])

  const handleCompare = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和日期范围')
      return
    }
    setLoadingCompare(true)
    setCompareResult(null)
    try {
      await loadMootdxData()
      const response = await compareStrategies({
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        initial_capital: initialCapital,
      })
      setCompareResult(response)
      message.success(`对比完成: ${response.total_strategies} 个策略`)
    } catch (error) {
      message.error(getApiErrorMessage(error))
      logger.error(error)
    } finally {
      setLoadingCompare(false)
    }
  }, [stockCode, dateRange, initialCapital, loadMootdxData])

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
      <div className="page-header">
        <div
          className="flex flex-between"
          style={{ flexWrap: 'wrap', gap: 'var(--space-md)' }}
        >
          <div>
            <h1 className="page-title">策略研究</h1>
            <p className="page-subtitle">选择策略、配置参数、执行回测</p>
          </div>
        </div>
      </div>

      <div className="strategies-layout">
        <StrategyList
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          loading={loadingStrategies}
          onSelect={setSelectedStrategy}
        />

        <StrategyConfig
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          stockCode={stockCode}
          dateRange={dateRange}
          initialCapital={initialCapital}
          parameters={parameters}
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
          <BacktestDetails
            optimizeResult={optimizeResult}
            compareResult={compareResult}
            onRunBestBacktest={handleRunBacktest}
            onSelectStrategy={setSelectedStrategy}
          />
        </StrategyResults>
      </div>
    </div>
  )
}

export default Strategies
