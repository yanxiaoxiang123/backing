import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DLPrediction from '../DLPrediction'
import { getDLModels } from '../../services/dl'
import { getStock } from '../../services/stocks'

const experiment = vi.hoisted(() => ({
  running: false,
  saved: null,
  result: null as unknown,
  error: null,
  lastStatus: null,
  start: vi.fn(),
  cancel: vi.fn(),
}))
vi.mock('../../hooks/useDLExperiment', () => ({ useDLExperiment: () => experiment }))
vi.mock('../../services/dl', () => ({ getDLModels: vi.fn() }))
vi.mock('../../services/stocks', () => ({ getStock: vi.fn() }))
vi.mock('../../components/charts/LazyECharts', () => ({
  LazyECharts: () => <div>chart</div>,
}))
vi.mock('../../components/StockSearch', () => ({
  default: ({ id, onChange }: { id: string; onChange: (code: string) => void }) => (
    <input id={id} onChange={(e) => onChange(e.target.value)} />
  ),
}))

function setup() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DLPrediction />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
  experiment.result = null
  experiment.start.mockClear()
  vi.mocked(getStock).mockResolvedValue({
    id: 1,
    code: 'sh.600000',
    name: '浦发银行',
    market: 'sh',
    created_at: '',
  })
  vi.mocked(getDLModels).mockResolvedValue({
    models: [
      {
        id: 'kronos-small',
        name: 'Kronos-small',
        available: true,
        min_context: 60,
        max_context: 512,
        min_horizon: 1,
        max_horizon: 30,
      },
      {
        id: 'timesfm-2.5',
        name: 'TimesFM 2.5 200M',
        available: true,
        min_context: 60,
        max_context: 512,
        min_horizon: 1,
        max_horizon: 30,
        output_fields: ['close'],
      },
    ],
    remote: { available: true },
  })
})

it('defaults to Kronos-small with 256 bars and submits a 5-session experiment', async () => {
  const user = userEvent.setup()
  setup()
  await user.type(screen.getByLabelText('股票代码'), 'sh.600000')
  const submit = screen.getByRole('button', { name: /预测未来 5 个交易日/ })
  await waitFor(() => expect(submit).toBeEnabled())
  await user.click(submit)
  expect(experiment.start).toHaveBeenCalledWith('predict', {
    stock_code: 'sh.600000',
    model: 'kronos-small',
    kline_days: 256,
    prediction_days: 5,
  })
})

it('labels an earlier result with its original stock and model after settings change', async () => {
  experiment.result = {
    kind: 'predict',
    request: {
      stock_code: 'sh.600000',
      model: 'kronos-base',
      kline_days: 256,
      prediction_days: 1,
    },
    response: {
      success: true,
      data: {
        stock_code: 'sh.600000',
        model: 'kronos-base',
        current_price: 10,
        last_date: '2026-10-30',
        prediction_dates: ['2026-11-02'],
        predicted_prices: [11],
        kline_data: [
          { date: '2026-10-30', open: 10, high: 11, low: 9, close: 10, volume: 1000 },
        ],
      },
    },
  }
  setup()
  expect(
    screen.getByText(/当前显示原实验：sh.600000 · kronos-base/),
  ).toBeInTheDocument()
  expect(screen.getByText('预测末值').nextElementSibling).toHaveTextContent('11.00')
})

it('keeps presets, custom horizon and the submitted request synchronized', async () => {
  const user = userEvent.setup()
  setup()
  await user.type(screen.getByLabelText('股票代码'), 'sh.600000')
  await user.click(screen.getByRole('button', { name: '30日' }))
  expect(screen.getByLabelText('预测交易日数')).toHaveValue('30')
  const horizon = screen.getByLabelText('预测交易日数')
  await user.clear(horizon)
  await user.type(horizon, '17')
  expect(screen.getByRole('button', { name: '30日' })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  await user.click(screen.getByRole('button', { name: /预测未来 17 个交易日/ }))
  expect(experiment.start).toHaveBeenLastCalledWith(
    'predict',
    expect.objectContaining({
      prediction_days: 17,
    }),
  )
})

it('does not mark an identical experiment stale because JSON keys were ordered differently', () => {
  sessionStorage.setItem('backing_dl_stockCode', JSON.stringify('sh.600000'))
  experiment.result = {
    kind: 'predict',
    request: {
      stock_code: 'sh.600000',
      prediction_days: 5,
      kline_days: 256,
      model: 'kronos-small',
    },
    response: {
      success: true,
      data: {
        stock_code: 'sh.600000',
        model: 'kronos-small',
        current_price: 10,
        last_date: '2026-10-30',
        prediction_dates: ['2026-11-02'],
        predicted_prices: [11],
        kline_data: [],
      },
    },
  }
  setup()
  expect(screen.queryByText(/当前显示原实验/)).not.toBeInTheDocument()
})

it('submits a 30-session TimesFM experiment with the shared horizon controls', async () => {
  sessionStorage.setItem('backing_dl_model', JSON.stringify('timesfm-2.5'))
  const user = userEvent.setup()
  setup()
  await user.type(screen.getByLabelText('股票代码'), 'sh.600000')
  await user.click(screen.getByRole('button', { name: '30日' }))
  const submit = screen.getByRole('button', { name: /预测未来 30 个交易日/ })
  await waitFor(() => expect(submit).toBeEnabled())
  await user.click(submit)
  expect(experiment.start).toHaveBeenCalledWith(
    'predict',
    expect.objectContaining({
      model: 'timesfm-2.5',
      prediction_days: 30,
      kline_days: 256,
    }),
  )
})

it('labels TimesFM close predictions without showing fabricated future candles', () => {
  sessionStorage.setItem('backing_dl_model', JSON.stringify('timesfm-2.5'))
  experiment.result = {
    kind: 'predict',
    request: {
      model: 'timesfm-2.5',
      stock_code: 'sh.600000',
      kline_days: 256,
      prediction_days: 1,
    },
    response: {
      success: true,
      data: {
        stock_code: 'sh.600000',
        model: 'timesfm-2.5',
        forecast_target: 'close',
        current_price: 10,
        last_date: '2026-10-30',
        prediction_dates: ['2026-11-02'],
        predicted_prices: [11],
        kline_data: [],
      },
    },
  }
  setup()
  expect(screen.getByText(/TimesFM 收盘价点预测/)).toBeInTheDocument()
  expect(screen.queryByText('预测 K 线明细')).not.toBeInTheDocument()
})
