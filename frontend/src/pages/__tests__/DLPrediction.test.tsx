import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DLPrediction from '../DLPrediction'
import { getDLModels } from '../../services/dl'

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
  expect(screen.getByText('11.00')).toBeInTheDocument()
})
