import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Card,
  InputNumber,
  DatePicker,
  Button,
  Spin,
  Empty,
  message,
  Descriptions,
  Table,
  Tag,
  Select,
  Slider,
  Alert,
  Progress,
} from 'antd'
import {
  LoadingOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { LazyECharts } from '../components/charts/LazyECharts'
import type { EChartsOption, TooltipComponentFormatterCallbackParams } from 'echarts'
import {
  getDLModels,
  type DLForecast,
  type DLBacktest,
  type DLModelId,
  type DLExperimentRequest,
} from '../services/dl'
import { useDLExperiment } from '../hooks/useDLExperiment'
import StockSearch from '../components/StockSearch'
import { usePersistedState } from '../hooks/usePersistedState'
import dayjs from 'dayjs'
import { PageHeader } from '../components/research/ResearchPrimitives'

const { RangePicker } = DatePicker

function DLPrediction() {
  const experiment = useDLExperiment()
  const models = useQuery({
    queryKey: ['dl-models'],
    queryFn: getDLModels,
    refetchInterval: 15000,
  })
  const [model, setModel] = usePersistedState<DLModelId>('dl_model', 'kronos-small')
  const [predictionDays, setPredictionDays] = usePersistedState('dl_predictionDays', 5)
  const isKronos = model !== 'legacy'
  const selectedModel = models.data?.models.find((item) => item.id === model)

  // Form state
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

  const predictionResult =
    experiment.result?.kind === 'predict'
      ? (experiment.result.response.data as DLForecast)
      : null
  const backtestResult =
    experiment.result?.kind === 'backtest'
      ? (experiment.result.response.data as DLBacktest)
      : null
  const loadingPredict = experiment.running && experiment.saved?.kind === 'predict'
  const loadingBacktest = experiment.running && experiment.saved?.kind === 'backtest'
  const request: DLExperimentRequest = {
    model,
    stock_code: stockCode || '',
    kline_days: isKronos ? klineDays : Math.min(250, klineDays),
    prediction_days: isKronos ? predictionDays : 5,
  }
  const currentRequest =
    experiment.result?.kind === 'backtest'
      ? {
          ...request,
          start_date: dateRange[0],
          end_date: dateRange[1],
          initial_capital: initialCapital,
        }
      : request
  const staleResult =
    experiment.result &&
    JSON.stringify(experiment.result.request) !== JSON.stringify(currentRequest)
  const handlePredict = () => {
    if (!stockCode) {
      message.warning('请选择股票')
      return
    }

    experiment.start('predict', request)
  }

  const handleBacktest = () => {
    if (!stockCode || !dateRange[0] || !dateRange[1]) {
      message.warning('请选择股票和回测区间')
      return
    }

    experiment.start('backtest', {
      ...request,
      start_date: dateRange[0],
      end_date: dateRange[1],
      initial_capital: initialCapital,
    })
  }

  const chartOption = useMemo<EChartsOption>(() => {
    if (
      !predictionResult ||
      !Array.isArray(predictionResult.kline_data) ||
      predictionResult.kline_data.length === 0
    ) {
      return {}
    }

    const klineData = predictionResult.kline_data
    const dates = klineData.map((d) => d.date)
    const closePrices = klineData.map((d) => d.close)

    // 预测数据
    const predictionDates = predictionResult.prediction_dates || []
    const predictedPrices = predictionResult.predicted_prices || []

    // 合并所有日期用于x轴
    const allDates = [...dates, ...predictionDates]

    // 预测起点索引（历史数据的最后一天）
    const predictionStartIndex = dates.length - 1

    return {
      backgroundColor: '#fff',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['历史价格', '预测价格'],
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' },
      },
      grid: [{ left: '10%', right: '8%', height: '70%' }],
      xAxis: {
        type: 'category',
        data: allDates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: {
          color: 'var(--color-text-tertiary)',
          fontSize: 10,
          hideOverlap: true,
        },
        splitLine: { show: false },
      },
      yAxis: {
        scale: true,
        splitArea: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
      },
      dataZoom: [
        {
          type: 'inside',
          start: 50,
          end: 100,
        },
        {
          show: true,
          type: 'slider',
          bottom: 10,
          start: 50,
          end: 100,
          height: 20,
          borderColor: 'var(--color-border)',
          backgroundColor: 'var(--color-bg-secondary)',
          fillerColor: 'rgba(0, 113, 227, 0.1)',
          handleStyle: { color: 'var(--color-ink)' },
        },
      ],
      series: [
        {
          name: '历史价格',
          type: 'line',
          data: [...closePrices, ...Array(predictionDates.length).fill(null)],
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#0071e3',
            width: 2,
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 113, 227, 0.2)' },
                { offset: 1, color: 'rgba(0, 113, 227, 0.02)' },
              ],
            },
          },
        },
        {
          name: '预测价格',
          type: 'line',
          data: [
            ...Array(dates.length - 1).fill(null),
            closePrices[closePrices.length - 1],
            ...predictedPrices,
          ],
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: {
            color: '#ff3b30',
            width: 2,
            type: 'dashed',
          },
          itemStyle: {
            color: '#ff3b30',
          },
        },
        {
          name: '预测起点',
          type: 'line',
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              {
                xAxis: predictionStartIndex,
                lineStyle: {
                  color: '#ff9500',
                  width: 2,
                  type: 'solid',
                },
                label: {
                  show: true,
                  position: 'insideEndTop',
                  rotate: 0,
                  formatter: '预测起点',
                  color: '#ff9500',
                  fontSize: 11,
                },
              },
            ],
          },
        },
      ],
    }
  }, [predictionResult])

  const backtestChartOption = useMemo<EChartsOption>(() => {
    if (!backtestResult || !backtestResult.dates || backtestResult.dates.length === 0) {
      return {}
    }

    const dates = backtestResult.dates
    const closePrices = backtestResult.close_prices
    const trades = backtestResult.trades || []

    // 提取买卖点
    const buyPoints: { date: string; price: number; profit?: number }[] = []
    const sellPoints: {
      date: string
      price: number
      return?: number
      profit?: number
    }[] = []

    trades.forEach((trade) => {
      if (trade.action === 'BUY') {
        buyPoints.push({ date: trade.date, price: trade.price })
      } else {
        sellPoints.push({
          date: trade.date,
          price: trade.price,
          return: trade.return,
          profit: trade.profit,
        })
      }
    })

    // 买卖点对应的索引
    const buyData = buyPoints.map((p) => ({
      value: [p.date, p.price],
      itemStyle: { color: '#34c759', borderColor: '#fff', borderWidth: 1 },
    }))
    const sellData = sellPoints.map((p) => ({
      value: [p.date, p.price, p.profit],
      itemStyle: { color: '#ff3b30', borderColor: '#fff', borderWidth: 1 },
    }))

    return {
      backgroundColor: '#fff',
      animation: false,
      legend: {
        top: 10,
        left: 'center',
        textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
        data: ['收盘价', '买入', '卖出'],
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#fff',
        borderColor: 'var(--color-border)',
        textStyle: { color: 'var(--color-text-primary)' },
        formatter: (params: TooltipComponentFormatterCallbackParams) => {
          const list = Array.isArray(params) ? params : [params]
          if (list.length === 0) return ''
          const date = String(
            (list[0] as unknown as { axisValue?: string }).axisValue ?? '',
          )
          const price = (list[0].data as [string, number])[1]
          let html = `<div style="font-weight:500">${date}</div>`
          html += `<div>价格: <span style="color:#0071e3;font-weight:500">${price.toFixed(2)}</span></div>`

          const buy = buyPoints.find((p) => p.date === date)
          const sell = sellPoints.find((p) => p.date === date)
          if (buy) {
            html += `<div style="color:#34c759">买入: ${buy.price.toFixed(2)}</div>`
          }
          if (sell) {
            const color = (sell.profit ?? 0) >= 0 ? '#34c759' : '#ff3b30'
            const sign = (sell.profit ?? 0) >= 0 ? '+' : ''
            html += `<div style="color:${color}">卖出: ${sell.price.toFixed(2)}</div>`
            html += `<div style="color:${color}">收益: ${sign}${sell.profit?.toFixed(2)} (${sign}${sell.return?.toFixed(2)}%)</div>`
          }
          return html
        },
      },
      grid: [{ left: '10%', right: '8%', top: '15%', height: '70%' }],
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
        splitLine: { show: false },
      },
      yAxis: {
        scale: true,
        splitArea: { show: false },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100,
        },
        {
          show: true,
          type: 'slider',
          bottom: 10,
          start: 0,
          end: 100,
          height: 20,
          borderColor: 'var(--color-border)',
          backgroundColor: 'var(--color-bg-secondary)',
          fillerColor: 'rgba(0, 113, 227, 0.1)',
          handleStyle: { color: 'var(--color-ink)' },
        },
      ],
      series: [
        {
          name: '收盘价',
          type: 'line',
          data: closePrices,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#0071e3',
            width: 2,
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(0, 113, 227, 0.2)' },
                { offset: 1, color: 'rgba(0, 113, 227, 0.02)' },
              ],
            },
          },
        },
        {
          name: '买入',
          type: 'scatter',
          data: buyData,
          symbol: 'triangle',
          symbolSize: 10,
          zlevel: 10,
        },
        {
          name: '卖出',
          type: 'scatter',
          data: sellData,
          symbol: 'triangle',
          symbolSize: 10,
          symbolRotate: 180,
          zlevel: 10,
        },
      ],
    }
  }, [backtestResult])

  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (action: string) => (
        <Tag color={action.toUpperCase() === 'BUY' ? 'green' : 'red'}>
          {action.toUpperCase() === 'BUY' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (v: number) => v.toFixed(2),
    },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    {
      title: '金额',
      key: 'amount',
      render: (_: number | undefined, record: DLBacktest['trades'][number]) => {
        const amount =
          record.action === 'BUY'
            ? (record.cost ?? record.price * record.quantity)
            : (record.revenue ?? record.price * record.quantity)
        return amount.toFixed(2)
      },
    },
    {
      title: '收益率',
      key: 'return',
      render: (_: number | undefined, record: DLBacktest['trades'][number]) => {
        if (record.action === 'BUY' || record.return === undefined) return '-'
        const color = record.return >= 0 ? '#34c759' : '#ff3b30'
        const sign = record.return >= 0 ? '+' : ''
        return (
          <span style={{ color }}>
            {sign}
            {record.return.toFixed(2)}%
          </span>
        )
      },
    },
  ]

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="MODEL LAB"
        title="DL 预测"
        subtitle="选择 Kronos 或现有预测器，研究未来行情并验证历史表现"
      />
      {experiment.error && <Alert type="error" showIcon message={experiment.error} />}
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
          action={<Button onClick={() => void experiment.cancel()}>取消任务</Button>}
        />
      )}
      {staleResult && (
        <Alert
          type="warning"
          message={`当前显示原实验：${experiment.result?.request.stock_code} · ${experiment.result?.request.model}，配置已变更`}
        />
      )}

      <div className="dl-lab-layout">
        {/* Left: Configuration */}
        <Card
          title={
            <>
              <LineChartOutlined style={{ marginRight: 8 }} />
              预测配置
            </>
          }
          style={{ position: 'sticky', top: 80 }}
        >
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}
          >
            <div>
              <label htmlFor="dl-model">预测模型</label>
              <Select
                id="dl-model"
                value={model}
                style={{ width: '100%' }}
                disabled={experiment.running}
                onChange={(value: DLModelId) => {
                  setModel(value)
                  if (value === 'legacy') {
                    setKlineDays(Math.min(250, klineDays))
                    setPredictionDays(5)
                  } else {
                    setKlineDays(Math.max(60, klineDays))
                  }
                }}
                options={[
                  { value: 'kronos-small', label: 'Kronos-small' },
                  { value: 'kronos-base', label: 'Kronos-base' },
                  { value: 'legacy', label: '现有预测器（含技术指标降级）' },
                ]}
              />
            </div>
            {isKronos && (!selectedModel?.available || models.isError) && (
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
            {/* Stock Selection */}
            <div>
              <label htmlFor="dl-stock">股票代码</label>
              <StockSearch
                id="dl-stock"
                value={stockCode ?? undefined}
                onChange={(code) => setStockCode(code)}
              />
            </div>

            {/* Kline Days */}
            <div>
              <label
                htmlFor="dl-context"
                style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-xs)',
                }}
              >
                历史K线天数
              </label>
              <InputNumber
                id="dl-context"
                value={klineDays}
                onChange={(value) => setKlineDays(value ?? 60)}
                min={isKronos ? 60 : 30}
                max={isKronos ? 512 : 250}
                step={10}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label htmlFor="dl-horizon">预测交易日数</label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-md)',
                }}
              >
                <Slider
                  ariaLabelForHandle="滑动选择预测天数"
                  value={isKronos ? predictionDays : 5}
                  min={1}
                  max={30}
                  step={1}
                  marks={{ 1: '1', 15: '15', 30: '30' }}
                  disabled={!isKronos || experiment.running}
                  onChange={setPredictionDays}
                  tooltip={{ formatter: (value) => `${value} 个交易日` }}
                  style={{ flex: 1, minWidth: 0 }}
                />
                <InputNumber
                  id="dl-horizon"
                  value={isKronos ? predictionDays : 5}
                  min={1}
                  max={30}
                  step={1}
                  precision={0}
                  disabled={!isKronos || experiment.running}
                  onChange={(value) => {
                    if (value !== null)
                      setPredictionDays(Math.min(30, Math.max(1, Math.round(value))))
                  }}
                  style={{ width: 80, flexShrink: 0 }}
                />
              </div>
            </div>

            {/* Buttons */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-sm)',
                marginTop: 'var(--space-md)',
              }}
            >
              <Button
                type="primary"
                icon={<LineChartOutlined />}
                onClick={handlePredict}
                loading={loadingPredict}
                disabled={
                  !stockCode ||
                  experiment.running ||
                  (isKronos && !selectedModel?.available)
                }
                block
              >
                预测未来 {isKronos ? predictionDays : 5} 个交易日
              </Button>
            </div>

            <div
              style={{
                borderTop: '1px solid var(--color-border)',
                paddingTop: 'var(--space-md)',
                marginTop: 'var(--space-md)',
              }}
            >
              <label
                htmlFor="dl-dates"
                style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-xs)',
                }}
              >
                回测区间
              </label>
              <RangePicker
                id={{ start: 'dl-dates', end: 'dl-end-date' }}
                value={[dayjs(dateRange[0]), dayjs(dateRange[1])]}
                onChange={(dates) => {
                  if (dates) {
                    setDateRange([
                      dates[0]!.format('YYYY-MM-DD'),
                      dates[1]!.format('YYYY-MM-DD'),
                    ])
                  }
                }}
                style={{ width: '100%' }}
              />

              <label
                htmlFor="dl-capital"
                style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-xs)',
                  marginTop: 'var(--space-md)',
                }}
              >
                初始资金
              </label>
              <InputNumber
                id="dl-capital"
                value={initialCapital}
                onChange={(value) => setInitialCapital(value ?? 100000)}
                min={10000}
                step={10000}
                style={{ width: '100%' }}
                formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                parser={(value) => Number(value!.replace(/\$\s?|(,*)/g, ''))}
              />

              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleBacktest}
                loading={loadingBacktest}
                disabled={
                  !stockCode ||
                  experiment.running ||
                  (isKronos && !selectedModel?.available)
                }
                style={{ marginTop: 'var(--space-md)', width: '100%' }}
              >
                执行回测
              </Button>
              {isKronos && (
                <p>
                  每 5 个交易日生成 5
                  日预测，下一交易日开盘执行。历史回溯不等于独立样本外验证。
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Middle: Chart */}
        <Card
          title={backtestResult ? '回测图表' : '价格走势'}
          style={{ minHeight: 400 }}
        >
          {loadingBacktest ? (
            <div className="loading-container">
              <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            </div>
          ) : backtestResult ? (
            <LazyECharts
              option={backtestChartOption}
              style={{ height: 400 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : loadingPredict ? (
            <div className="loading-container">
              <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            </div>
          ) : predictionResult ? (
            <LazyECharts
              option={chartOption}
              style={{ height: 400 }}
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <Empty
              description="配置模型与股票后，运行预测或回测查看图表"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ padding: 'var(--space-2xl)' }}
            />
          )}
        </Card>

        {/* Right: Results */}
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}
        >
          {/* Prediction Results */}
          {predictionResult && (
            <Card title="预测结果">
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="股票代码">
                  {predictionResult.stock_code}
                </Descriptions.Item>
                <Descriptions.Item label="实际模型">
                  {predictionResult.prediction_backend === 'technical_indicator'
                    ? '技术指标降级预测（非神经网络）'
                    : predictionResult.model || '现有预测器'}
                </Descriptions.Item>
                <Descriptions.Item label="预测期限">
                  {predictionResult.prediction_dates.length} 个交易日
                </Descriptions.Item>
                <Descriptions.Item label="输入区间">
                  {predictionResult.input_start || predictionResult.kline_data[0]?.date}{' '}
                  至 {predictionResult.last_date}
                </Descriptions.Item>
                <Descriptions.Item label="总耗时">
                  {((predictionResult.execution_time_ms || 0) / 1000).toFixed(1)} 秒
                </Descriptions.Item>
                <Descriptions.Item label="当前价格">
                  {predictionResult.current_price.toFixed(2)}
                </Descriptions.Item>
                <Descriptions.Item label="最后交易日">
                  {predictionResult.last_date}
                </Descriptions.Item>
              </Descriptions>

              <div style={{ marginTop: 'var(--space-md)' }}>
                <h4 style={{ marginBottom: 'var(--space-sm)' }}>
                  未来 {predictionResult.prediction_dates.length} 个交易日预测
                </h4>
                <Table
                  dataSource={predictionResult.prediction_dates.map((date, index) => ({
                    key: index,
                    date,
                    predicted_price: predictionResult.predicted_prices[index],
                    change:
                      index > 0
                        ? (
                            ((predictionResult.predicted_prices[index] -
                              predictionResult.predicted_prices[index - 1]) /
                              predictionResult.predicted_prices[index - 1]) *
                            100
                          ).toFixed(2)
                        : (
                            ((predictionResult.predicted_prices[0] -
                              predictionResult.current_price) /
                              predictionResult.current_price) *
                            100
                          ).toFixed(2),
                  }))}
                  columns={[
                    { title: '日期', dataIndex: 'date', key: 'date' },
                    {
                      title: '预测价格',
                      dataIndex: 'predicted_price',
                      key: 'predicted_price',
                      render: (v: number) => v.toFixed(2),
                    },
                    {
                      title: '涨跌幅',
                      dataIndex: 'change',
                      key: 'change',
                      render: (v: string) => (
                        <span style={{ color: Number(v) >= 0 ? '#34c759' : '#ff3b30' }}>
                          {Number(v) >= 0 ? '+' : ''}
                          {v}%
                        </span>
                      ),
                    },
                  ]}
                  pagination={false}
                  size="small"
                />
                {predictionResult.predicted_klines && (
                  <>
                    <h4>预测 K 线明细</h4>
                    <p>
                      三条采样路径的均值，非统计置信区间；不满足 OHLC
                      约束的输出保留并标记。
                    </p>
                    <Table
                      dataSource={predictionResult.predicted_klines}
                      rowKey="date"
                      size="small"
                      scroll={{ x: 640 }}
                      pagination={false}
                      columns={[
                        { title: '日期', dataIndex: 'date', width: 110 },
                        ...(['open', 'high', 'low', 'close'] as const).map(
                          (field, i) => ({
                            title: ['开盘', '最高', '最低', '收盘'][i],
                            dataIndex: field,
                            render: (value: number) => value.toFixed(2),
                          }),
                        ),
                        {
                          title: '成交量/股',
                          dataIndex: 'volume',
                          render: (v: number) => v.toFixed(0),
                        },
                        {
                          title: '成交额/元',
                          dataIndex: 'amount',
                          render: (v: number) => v.toFixed(0),
                        },
                        {
                          title: '校验',
                          dataIndex: 'ohlc_valid',
                          render: (v: boolean) => (v ? '有效' : 'OHLC 无效'),
                        },
                      ]}
                    />
                  </>
                )}
              </div>
            </Card>
          )}

          {/* Backtest Results */}
          {backtestResult && (
            <Card title="回测结果">
              <p>
                {backtestResult.experiment?.stock_code} ·{' '}
                {backtestResult.model || '现有预测器'} ·{' '}
                {backtestResult.experiment?.start_date} 至{' '}
                {backtestResult.experiment?.end_date}
              </p>
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="总收益率">
                  <span
                    style={{
                      color: backtestResult.total_return >= 0 ? '#34c759' : '#ff3b30',
                    }}
                  >
                    {backtestResult.total_return.toFixed(2)}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="年化收益率">
                  <span
                    style={{
                      color:
                        backtestResult.annualized_return >= 0 ? '#34c759' : '#ff3b30',
                    }}
                  >
                    {backtestResult.annualized_return.toFixed(2)}%
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="夏普比率">
                  {backtestResult.sharpe_ratio.toFixed(4)}
                </Descriptions.Item>
                <Descriptions.Item label="最大回撤">
                  {backtestResult.max_drawdown.toFixed(2)}%
                </Descriptions.Item>
                <Descriptions.Item label="胜率">
                  {backtestResult.win_rate.toFixed(2)}%
                </Descriptions.Item>
                <Descriptions.Item label="交易次数">
                  {backtestResult.total_trades}
                </Descriptions.Item>
              </Descriptions>

              <div style={{ marginTop: 'var(--space-md)' }}>
                <h4 style={{ marginBottom: 'var(--space-sm)' }}>交易记录</h4>
                <Table
                  dataSource={backtestResult.trades}
                  columns={tradeColumns}
                  rowKey={(record) => `${record.date}-${record.action}-${record.price}`}
                  size="small"
                  pagination={{ pageSize: 10 }}
                  scroll={{ y: 300 }}
                />
              </div>
            </Card>
          )}

          {!predictionResult && !backtestResult && (
            <Card className="dl-model-brief" title="模型状态">
              <div className="dl-model-status">
                <span className="status-dot status-dot--idle" />
                <strong>等待实验</strong>
              </div>
              <p>
                选择股票后可运行预测或回测。结果会保存在当前会话，不会覆盖历史数据。
              </p>
              <dl>
                <div>
                  <dt>预测范围</dt>
                  <dd>{isKronos ? '未来 1–30 个交易日' : '未来 5 个交易日'}</dd>
                </div>
                <div>
                  <dt>建议样本</dt>
                  <dd>{isKronos ? '默认 256 根，最大 512 根' : '至少 60 个交易日'}</dd>
                </div>
                <div>
                  <dt>数据来源</dt>
                  <dd>本地行情服务</dd>
                </div>
              </dl>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default DLPrediction
