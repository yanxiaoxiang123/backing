import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { message } from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  getStrategies,
  generateSignals,
  runStrategyBacktest,
  submitOptimizeParameters,
  getStockIndicators,
  compareStrategies,
  getApiErrorMessage,
} from '../services/api'
import { logger } from '../utils/logger'
import { usePersistedState } from '../hooks/usePersistedState'
import { useJobPolling } from '../hooks/useJobPolling'
import { getChartOption, KlineData } from '../utils/chart'
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

  const handleGenerateSignals = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingSignals(true)
    setBacktestResult(null)
    setOptimizeResult(null)
    try {
      const response = await generateSignals({
        strategy_name: selectedStrategy,
        stock_code: stockCode,
        start_date: dateRange[0],
        end_date: dateRange[1],
        parameters,
      })
      setSignals(response.data)
      setSignalStats(response.stats ?? null)

      const klineResponse = await getStockIndicators(
        stockCode,
        'daily',
        dateRange[0],
        dateRange[1],
      )
      if (klineResponse.data) {
        setKlineData(klineResponse.data)
      }
    } catch (error) {
      message.error('生成信号失败')
      logger.error(error)
    } finally {
      setLoadingSignals(false)
    }
  }, [selectedStrategy, stockCode, dateRange, parameters])

  const handleRunBacktest = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingBacktest(true)
    try {
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
    } catch (error) {
      message.error('回测执行失败')
      logger.error(error)
    } finally {
      setLoadingBacktest(false)
    }
  }, [selectedStrategy, stockCode, dateRange, initialCapital, parameters])

  const handleOptimize = useCallback(async () => {
    if (!selectedStrategy || !stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择策略、股票和日期范围')
      return
    }

    setLoadingOptimize(true)
    try {
      const strategy = strategies.find((s) => s.name === selectedStrategy)
      if (!strategy) return

      const paramGrid: Record<string, number[]> = {}
      Object.entries(strategy.parameters).forEach(([key, config]) => {
        if (
          config.type === 'slider' &&
          config.min !== undefined &&
          config.max !== undefined
        ) {
          if (
            selectedStrategy === 'lstm_5d' &&
            !['buy_threshold', 'sell_threshold', 'min_confidence'].includes(key)
          ) {
            return
          }
          const step = config.step || 1
          const values: number[] = []
          for (let v = config.min; v <= config.max; v += step) {
            values.push(v)
          }
          paramGrid[key] = values
        }
      })

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
  }, [selectedStrategy, stockCode, dateRange, initialCapital, strategies, waitForJob])

  const handleCompare = useCallback(async () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和日期范围')
      return
    }
    setLoadingCompare(true)
    setCompareResult(null)
    try {
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
  }, [stockCode, dateRange, initialCapital])

  const getCurrentChartOption = useMemo(
    () => getChartOption(klineData, signals, backtestResult),
    [klineData, signals, backtestResult],
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
        >
          <BacktestDetails
            signalStats={signalStats}
            backtestResult={backtestResult}
            optimizeResult={optimizeResult}
            compareResult={compareResult}
          />
        </StrategyResults>
      </div>
    </div>
  )
}

export default Strategies
