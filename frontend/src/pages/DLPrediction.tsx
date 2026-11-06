import { ParameterSlider } from '../components/ParameterSlider'
import { Prose } from '../components/Prose'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  ConfigProvider,
  DatePicker,
  Descriptions,
  Drawer,
  Empty,
  InputNumber,
  Progress,
  Segmented,
  Select,
  Spin,
  message,
} from 'antd'
import {
  ClockCircleOutlined,
  DownloadOutlined,
  HistoryOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { LazyECharts } from '../components/charts/LazyECharts'
import { ChartResetButton } from '../components/charts/ChartResetButton'
import { QueryStatus } from '../components/research/QueryStatus'
import { FinancialValue } from '../components/research/FinancialValue'
import {
  formatNumber,
  formatDateTime,
  formatDate,
  formatPercent,
} from '../utils/dataFormat'
import {
  forecastChartOption,
  backtestChartOption,
} from '../components/charts/dlChartOptions'
import {
  DLForecastDetails,
  DLBacktestDetails,
} from '../components/charts/DLResultDetails'
import StockSearch from '../components/StockSearch'
import { useDLExperiment } from '../hooks/useDLExperiment'
import { usePersistedState } from '../hooks/usePersistedState'
import {
  getDLModels,
  type DLForecast,
  type DLBacktest,
  type DLModelId,
  type DLExperimentKind,
  type DLExperimentRequest,
} from '../services/dl'
import { getStock } from '../services/stocks'
import '../styles/dl-prediction.css'

const { RangePicker } = DatePicker
const price = (value?: number) => formatNumber(value)
const time = formatDateTime
const date = formatDate

function DLPrediction() {
  const experiment = useDLExperiment()
  const models = useQuery({
    queryKey: ['dl-models'],
    queryFn: getDLModels,
    refetchInterval: 15000,
  })
  const [model, setModel] = usePersistedState<DLModelId>('dl_model', 'kronos-small')
  const [predictionDays, setPredictionDays] = usePersistedState('dl_predictionDays', 5)
  const [stockCode, setStockCode] = usePersistedState<string | null>(
    'dl_stockCode',
    null,
  )
  const [klineDays, setKlineDays] = usePersistedState('dl_klineDays', 256)
  const [dateRange, setDateRange] = usePersistedState<[string, string]>(
    'dl_dateRange',
    [dayjs().subtract(1, 'year').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
  )
  const [initialCapital, setInitialCapital] = usePersistedState(
    'dl_initialCapital',
    100000,
  )
  const [chartView, setChartView] = useState<DLExperimentKind>('predict')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [chartResetKey, setChartResetKey] = useState(0)
  const isRemoteModel = model !== 'legacy'
  const selectedModel = models.data?.models.find((item) => item.id === model)
  const horizon = isRemoteModel ? predictionDays : 5

  useEffect(() => {
    if (experiment.result) setChartView(experiment.result.kind)
  }, [experiment.result])

  const shownExperiment =
    experiment.results?.[chartView] ??
    (experiment.result?.kind === chartView ? experiment.result : null)
  const predictionResult =
    shownExperiment?.kind === 'predict'
      ? (shownExperiment.response.data as DLForecast)
      : null
  const backtestResult =
    shownExperiment?.kind === 'backtest'
      ? (shownExperiment.response.data as DLBacktest)
      : null
  const loadingPredict = experiment.running && experiment.saved?.kind === 'predict'
  const loadingBacktest = experiment.running && experiment.saved?.kind === 'backtest'
  const chartLoading = chartView === 'predict' ? loadingPredict : loadingBacktest
  const displayedCode = shownExperiment?.request.stock_code || stockCode
  const stock = useQuery({
    queryKey: ['dl-stock-info', displayedCode],
    queryFn: () => getStock(displayedCode!),
    enabled: Boolean(displayedCode),
    staleTime: 5 * 60_000,
  })
  const cutoff =
    predictionResult?.last_date ||
    backtestResult?.dates[backtestResult.dates.length - 1]
  const request: DLExperimentRequest = {
    model,
    stock_code: stockCode || '',
    kline_days: isRemoteModel ? klineDays : Math.min(250, klineDays),
    prediction_days: horizon,
  }
  const currentRequest =
    chartView === 'backtest'
      ? {
          ...request,
          start_date: dateRange[0],
          end_date: dateRange[1],
          initial_capital: initialCapital,
        }
      : request
  const comparisonFields: Array<keyof DLExperimentRequest> = [
    'model',
    'stock_code',
    'kline_days',
    'prediction_days',
    ...(chartView === 'backtest'
      ? (['start_date', 'end_date', 'initial_capital'] as const)
      : []),
  ]
  const staleResult =
    shownExperiment &&
    comparisonFields.some(
      (field) => shownExperiment.request[field] !== currentRequest[field],
    )
  const disabled =
    !stockCode || experiment.running || (isRemoteModel && !selectedModel?.available)
  const handlePredict = () => {
    if (!stockCode) {
      message.warning('请选择股票')
      return
    }
    setChartView('predict')
    experiment.start('predict', request)
  }
  const handleBacktest = () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和回测区间')
      return
    }
    setChartView('backtest')
    experiment.start('backtest', {
      ...request,
      start_date: dateRange[0],
      end_date: dateRange[1],
      initial_capital: initialCapital,
    })
  }
  const exportResult = () => {
    if (!shownExperiment) return
    const blob = new Blob([JSON.stringify(shownExperiment, null, 2)], {
      type: 'application/json;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `dl-${shownExperiment.kind}-${shownExperiment.request.stock_code}-${shownExperiment.jobId || 'result'}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }
  const chartOption = useMemo(
    () =>
      chartView === 'predict'
        ? forecastChartOption(predictionResult)
        : backtestChartOption(backtestResult),
    [chartView, predictionResult, backtestResult],
  )
  const actualModelId = predictionResult?.model || backtestResult?.model
  const actualModel =
    predictionResult?.prediction_backend === 'technical_indicator'
      ? '技术指标降级预测（非神经网络）'
      : (actualModelId === 'legacy'
          ? '现有预测器'
          : actualModelId === 'timesfm-2.5'
            ? 'TimesFM 2.5 200M'
            : actualModelId?.replace(/^kronos/, 'Kronos')) ||
        (shownExperiment ? '现有预测器' : '—')
  const runStatus = experiment.running
    ? '运行中'
    : experiment.error
      ? '运行异常'
      : shownExperiment
        ? '运行完成'
        : '等待实验'
  const latestClose =
    predictionResult?.current_price ??
    backtestResult?.close_prices[backtestResult.close_prices.length - 1]
  const forecastLast =
    predictionResult?.predicted_prices[predictionResult.predicted_prices.length - 1]

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#222222',
          colorText: '#242424',
          colorTextSecondary: '#777777',
          colorBorder: '#dedede',
          colorBorderSecondary: '#e8e8e8',
          borderRadius: 7,
          controlHeight: 40,
          fontSize: 15,
        },
        components: {
          Button: { borderRadius: 7, controlHeight: 40 },
          Select: { borderRadius: 7, controlHeight: 40 },
          InputNumber: { borderRadius: 7, controlHeight: 40 },
          DatePicker: { borderRadius: 7, controlHeight: 36, fontSize: 14 },
        },
      }}
    >
      <div className="dl-prediction-page">
        <header className="dl-page-header">
          <div>
            <Prose as="p" className="dl-eyebrow">
              MODEL LAB
            </Prose>
            <Prose as="h1">DL 预测</Prose>
            <Prose as="p" className="dl-subtitle">
              选择模型预测未来行情，并验证历史表现
            </Prose>
          </div>
          <div className="dl-header-actions">
            <Button icon={<HistoryOutlined />} onClick={() => setHistoryOpen(true)}>
              历史记录
            </Button>
            <Button
              icon={<DownloadOutlined />}
              disabled={!shownExperiment}
              onClick={exportResult}
            >
              导出结果
            </Button>
          </div>
        </header>
        <div className="dl-instrument-strip" aria-label="当前分析股票">
          <div className="dl-instrument-name">
            <strong>
              {stock.data?.name || (displayedCode ? '当前股票' : '请选择股票')}
            </strong>
            {displayedCode && (
              <span className="dl-instrument-code">{displayedCode.toUpperCase()}</span>
            )}
            {displayedCode && <span className="dl-market-label">A股</span>}
          </div>
          <span className="dl-data-cutoff">
            {cutoff ? `数据截至 ${date(cutoff)}` : '数据截止日期将在实验完成后显示'}
          </span>
        </div>
        <div className="dl-alerts">
          {experiment.error && (
            <Alert type="error" showIcon message={experiment.error} />
          )}
          {experiment.running && (
            <Alert
              role="status"
              type="info"
              message={experiment.lastStatus?.message || '正在提交实验'}
              description={
                <Progress
                  percent={Math.round((experiment.lastStatus?.progress || 0) * 100)}
                />
              }
              action={
                <Button onClick={() => void experiment.cancel()}>取消任务</Button>
              }
            />
          )}
          {staleResult && (
            <Alert
              type="warning"
              message={`当前显示原实验：${shownExperiment.request.stock_code} · ${shownExperiment.request.model}，配置已变更`}
            />
          )}
        </div>
        <div className="dl-lab-layout">
          <section className="dl-config-panel" aria-labelledby="dl-config-title">
            <div className="dl-panel-heading">
              <Prose as="h2" id="dl-config-title">
                <LineChartOutlined />
                预测配置
              </Prose>
            </div>
            <div className="dl-config-body">
              <div className="dl-field">
                <label htmlFor="dl-model">预测模型</label>
                <Select
                  id="dl-model"
                  value={model}
                  disabled={experiment.running}
                  onChange={(value: DLModelId) => {
                    setModel(value)
                    if (value === 'legacy') {
                      setKlineDays(Math.min(250, klineDays))
                      setPredictionDays(5)
                    } else setKlineDays(Math.max(60, klineDays))
                  }}
                  options={[
                    { value: 'kronos-small', label: 'Kronos-small' },
                    { value: 'kronos-base', label: 'Kronos-base' },
                    { value: 'timesfm-2.5', label: 'TimesFM 2.5 200M' },
                    { value: 'legacy', label: '现有预测器（含技术指标降级）' },
                  ]}
                />
              </div>
              {model === 'timesfm-2.5' && (
                <Prose as="p" className="dl-research-note">
                  使用历史收盘价预测未来收盘价，不生成其他 K 线字段。
                </Prose>
              )}
              {isRemoteModel && (!selectedModel?.available || models.isError) && (
                <Alert
                  type="warning"
                  message={
                    selectedModel?.reason ||
                    (models.isError ? '模型状态读取失败' : '正在检测远程模型')
                  }
                  action={
                    <Button size="small" onClick={() => void models.refetch()}>
                      重试
                    </Button>
                  }
                />
              )}
              <div className="dl-field">
                <label htmlFor="dl-stock">股票代码</label>
                <StockSearch
                  id="dl-stock"
                  value={stockCode ?? undefined}
                  disabled={experiment.running}
                  onChange={(code) => setStockCode(code)}
                />
              </div>
              <div className="dl-paired-fields">
                <div className="dl-field">
                  <label htmlFor="dl-context">历史 K 线</label>
                  <div className="dl-number-unit">
                    <InputNumber
                      id="dl-context"
                      value={klineDays}
                      disabled={experiment.running}
                      onChange={(value) => setKlineDays(value ?? 60)}
                      min={isRemoteModel ? 60 : 30}
                      max={isRemoteModel ? 512 : 250}
                      precision={0}
                      step={10}
                      controls={false}
                    />
                    <span>根</span>
                  </div>
                </div>
                <div className="dl-field">
                  <label htmlFor="dl-horizon">预测交易日数</label>
                  <div className="dl-number-unit">
                    <InputNumber
                      id="dl-horizon"
                      value={horizon}
                      min={1}
                      max={30}
                      precision={0}
                      controls={false}
                      disabled={!isRemoteModel || experiment.running}
                      onChange={(value) => {
                        if (value !== null)
                          setPredictionDays(
                            Math.min(30, Math.max(1, Math.round(value))),
                          )
                      }}
                    />
                    <span>天</span>
                  </div>
                </div>
              </div>
              <div className="dl-field">
                <span className="dl-field-label" id="dl-period-label">
                  周期选择
                </span>
                <div
                  className="dl-periods"
                  role="group"
                  aria-labelledby="dl-period-label"
                >
                  {[5, 15, 30].map((days) => (
                    <Button
                      key={days}
                      aria-pressed={horizon === days}
                      type={horizon === days ? 'primary' : 'default'}
                      disabled={!isRemoteModel || experiment.running}
                      onClick={() => setPredictionDays(days)}
                    >
                      {days}日
                    </Button>
                  ))}
                </div>
                <details className="dl-horizon-slider">
                  <summary>滑动微调天数</summary>
                  <ParameterSlider
                    ariaLabelForHandle="滑动选择预测天数"
                    value={horizon}
                    min={1}
                    max={30}
                    step={1}
                    marks={{ 1: '1', 15: '15', 30: '30' }}
                    disabled={!isRemoteModel || experiment.running}
                    onChange={setPredictionDays}
                    onChangeComplete={setPredictionDays}
                    tooltip={{ formatter: (value) => `${value} 个交易日` }}
                  />
                </details>
              </div>
              <Button
                type="primary"
                icon={<LineChartOutlined />}
                onClick={handlePredict}
                loading={loadingPredict}
                disabled={disabled}
                block
              >
                预测未来 {horizon} 个交易日
              </Button>
              <section
                className="dl-backtest-config"
                aria-labelledby="dl-backtest-title"
              >
                <Prose as="h2" id="dl-backtest-title">
                  <ClockCircleOutlined />
                  历史回测
                </Prose>
                <div className="dl-field">
                  <label htmlFor="dl-dates">回测区间</label>
                  <RangePicker
                    id={{ start: 'dl-dates', end: 'dl-end-date' }}
                    disabled={experiment.running}
                    value={[dayjs(dateRange[0]), dayjs(dateRange[1])]}
                    format="YYYY.MM.DD"
                    allowClear={false}
                    onChange={(dates) => {
                      if (dates?.[0] && dates[1])
                        setDateRange([
                          dates[0].format('YYYY-MM-DD'),
                          dates[1].format('YYYY-MM-DD'),
                        ])
                    }}
                  />
                </div>
                <div className="dl-field">
                  <label htmlFor="dl-capital">初始资金</label>
                  <div className="dl-number-unit">
                    <InputNumber
                      id="dl-capital"
                      value={initialCapital}
                      disabled={experiment.running}
                      onChange={(value) => setInitialCapital(value ?? 100000)}
                      min={10000}
                      step={10000}
                      controls={false}
                      formatter={(value) =>
                        `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
                      }
                      parser={(value) => Number(value?.replace(/,/g, '') || 0)}
                    />
                    <span>元</span>
                  </div>
                </div>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleBacktest}
                  loading={loadingBacktest}
                  disabled={disabled}
                  block
                >
                  执行回测
                </Button>
                <Prose as="p" className="dl-config-note">
                  {isRemoteModel
                    ? '每 5 个交易日滚动预测，下一交易日开盘执行。历史回溯不等于独立样本外验证。'
                    : '使用现有预测器回测，结果包含实际交易费用。'}
                </Prose>
              </section>
            </div>
          </section>
          <div className="dl-analysis-column">
            <section className="dl-chart-panel" aria-labelledby="dl-chart-title">
              <div className="dl-panel-heading">
                <Prose as="h2" id="dl-chart-title">
                  价格走势
                </Prose>
                <div className="research-chart-actions">
                  <QueryStatus fetching={chartLoading} label="实验运行中" />
                  <ChartResetButton
                    onReset={() => setChartResetKey((value) => value + 1)}
                  />
                  <Segmented
                    aria-label="图表类型"
                    value={chartView}
                    onChange={(value) => setChartView(value as DLExperimentKind)}
                    options={[
                      { value: 'predict', label: '价格预测' },
                      { value: 'backtest', label: '回测表现' },
                    ]}
                  />
                </div>
              </div>
              <dl className="dl-chart-metrics">
                <div>
                  <dt>最新收盘</dt>
                  <dd>
                    {price(latestClose)} <span>CNY</span>
                  </dd>
                </div>
                <div>
                  <dt>{chartView === 'predict' ? '预测末值' : '总收益率'}</dt>
                  <dd>
                    {chartView === 'predict' ? (
                      price(forecastLast)
                    ) : (
                      <FinancialValue value={backtestResult?.total_return} />
                    )}{' '}
                    {chartView === 'predict' && <span>CNY</span>}
                  </dd>
                </div>
                <div>
                  <dt>{chartView === 'predict' ? '预测周期' : '交易次数'}</dt>
                  <dd>
                    {(chartView === 'predict'
                      ? predictionResult?.prediction_dates.length
                      : backtestResult?.total_trades) ?? '—'}{' '}
                    <span>{chartView === 'predict' ? '交易日' : '次'}</span>
                  </dd>
                </div>
              </dl>
              <div className="dl-chart-area">
                {chartLoading &&
                !(chartView === 'predict'
                  ? predictionResult?.kline_data?.length
                  : backtestResult?.dates?.length) ? (
                  <div className="dl-chart-state" role="status">
                    <Spin />
                    <span>
                      正在运行{chartView === 'predict' ? '预测' : '回测'}实验…
                    </span>
                  </div>
                ) : predictionResult?.kline_data?.length ||
                  backtestResult?.dates?.length ? (
                  <LazyECharts
                    resetKey={chartResetKey}
                    option={chartOption}
                    notMerge
                    className="dl-price-chart"
                    opts={{ renderer: 'canvas' }}
                    summary={
                      chartView === 'predict'
                        ? '历史收盘价格与未来交易日预测价格，可缩放查看'
                        : '回测期间收盘价与实际买卖点，可缩放查看'
                    }
                  />
                ) : (
                  <div className="dl-chart-state">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        shownExperiment
                          ? '实验未返回可绘制的行情数据'
                          : `配置模型与股票后，运行${chartView === 'predict' ? '预测' : '回测'}查看图表`
                      }
                    />
                  </div>
                )}
              </div>
            </section>
            <section className="dl-results-panel" aria-labelledby="dl-results-title">
              <div className="dl-panel-heading">
                <Prose as="h2" id="dl-results-title">
                  {chartView === 'predict' ? '预测结果' : '回测结果'}
                </Prose>
                <span className="dl-run-status" role="status">
                  {runStatus}
                </span>
              </div>
              <div className="dl-results-body">
                {shownExperiment ? (
                  <Descriptions
                    column={{ xs: 1, sm: 1, md: 1, lg: 1, xl: 2, xxl: 2 }}
                    size="small"
                    bordered
                    className="dl-result-grid"
                  >
                    <Descriptions.Item label="股票代码">
                      {shownExperiment.request.stock_code}
                    </Descriptions.Item>
                    <Descriptions.Item label="实际模型">
                      {actualModel}
                    </Descriptions.Item>
                    <Descriptions.Item label="预测期限">
                      {shownExperiment.request.prediction_days} 个交易日
                      {predictionResult &&
                      predictionResult.prediction_dates.length !==
                        shownExperiment.request.prediction_days
                        ? `（实际返回 ${predictionResult.prediction_dates.length} 日）`
                        : ''}
                    </Descriptions.Item>
                    <Descriptions.Item label="历史窗口">
                      {shownExperiment.request.kline_days} 根 K 线
                    </Descriptions.Item>
                    <Descriptions.Item label="输入区间">
                      {predictionResult
                        ? `${date(predictionResult.input_start || predictionResult.kline_data[0]?.date)} — ${date(predictionResult.last_date)}`
                        : `${date(shownExperiment.request.start_date)} — ${date(shownExperiment.request.end_date)}`}
                    </Descriptions.Item>
                    <Descriptions.Item label="生成时间">
                      {time(shownExperiment.completedAt)}
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <div className="dl-results-empty">
                    <strong>等待实验</strong>
                    <Prose as="p">
                      选择股票后运行实验，模型、输入区间与预测结果将在这里展示。
                    </Prose>
                    <span>
                      {isRemoteModel
                        ? '未来 1–30 个交易日 · 默认 256 根 K 线'
                        : '未来 5 个交易日 · 最多 250 根 K 线'}{' '}
                      · 本地行情服务
                    </span>
                  </div>
                )}
                <Prose as="p" className="dl-research-note">
                  模型输出仅供研究，不构成投资建议
                </Prose>
                {shownExperiment?.response.data.execution_time_ms !== undefined && (
                  <Prose as="p" className="dl-execution-time">
                    总耗时{' '}
                    {formatNumber(
                      shownExperiment.response.data.execution_time_ms / 1000,
                      1,
                    )}{' '}
                    秒
                  </Prose>
                )}
              </div>
              {predictionResult && <DLForecastDetails result={predictionResult} />}
              {backtestResult && (
                <>
                  <Descriptions
                    column={2}
                    bordered
                    size="small"
                    className="dl-backtest-metrics"
                  >
                    <Descriptions.Item label="总收益率">
                      <FinancialValue value={backtestResult.total_return} />
                    </Descriptions.Item>
                    <Descriptions.Item label="年化收益率">
                      <FinancialValue value={backtestResult.annualized_return} />
                    </Descriptions.Item>
                    <Descriptions.Item label="夏普比率">
                      {formatNumber(backtestResult.sharpe_ratio, 4)}
                    </Descriptions.Item>
                    <Descriptions.Item label="最大回撤">
                      {formatPercent(backtestResult.max_drawdown)}
                    </Descriptions.Item>
                    <Descriptions.Item label="胜率">
                      {formatPercent(backtestResult.win_rate)}
                    </Descriptions.Item>
                    <Descriptions.Item label="交易次数">
                      {backtestResult.total_trades}
                    </Descriptions.Item>
                  </Descriptions>
                  <DLBacktestDetails result={backtestResult} />
                </>
              )}
            </section>
          </div>
        </div>
        <Drawer
          title="实验历史"
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
          width={440}
          rootClassName="dl-history-drawer"
        >
          <Prose as="p" className="dl-history-note">
            当前浏览器会话最近 20
            次成功实验。查看记录会读取原任务，不会重新提交预测或回测。
          </Prose>
          {experiment.history?.length ? (
            <div className="dl-history-list">
              {experiment.history.map((entry) => (
                <button
                  key={entry.jobId}
                  type="button"
                  disabled={experiment.running}
                  onClick={() => {
                    experiment.openHistory(entry)
                    setChartView(entry.kind)
                    setHistoryOpen(false)
                  }}
                >
                  <strong>
                    {entry.request.stock_code}{' '}
                    <span>{entry.kind === 'predict' ? '价格预测' : '历史回测'}</span>
                  </strong>
                  <span>
                    {entry.request.model} · {entry.request.prediction_days} 交易日 ·{' '}
                    {entry.request.kline_days} 根 K 线
                  </span>
                  <small>{time(entry.completedAt)}</small>
                </button>
              ))}
            </div>
          ) : (
            <Empty
              description="当前会话暂无已完成实验"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Drawer>
      </div>
    </ConfigProvider>
  )
}

export default DLPrediction
