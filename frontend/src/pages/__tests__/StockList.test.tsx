import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getStocks } from '../../services/stocks'
import StockList from '../StockList'

vi.mock('../../services/stocks', () => ({ getStocks: vi.fn() }))
vi.mock('../../services/api', async () => {
  const actual =
    await vi.importActual<typeof import('../../services/api')>('../../services/api')
  return {
    ...actual,
    submitSyncStocks: vi.fn(),
    submitSyncKline: vi.fn(),
  }
})

const mockedGetStocks = vi.mocked(getStocks)

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={['/stocks']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <StockList />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StockList', () => {
  beforeEach(() => {
    mockedGetStocks.mockReset()
  })

  it('renders server pagination totals and accessible research rows', async () => {
    mockedGetStocks.mockResolvedValue({
      items: [
        {
          id: 1,
          code: 'sh.600000',
          name: '浦发银行',
          market: 'sh',
          list_date: '1999-11-10',
          created_at: '2026-08-27T00:00:00Z',
        },
      ],
      total: 42,
      nextCursor: 1,
    })

    renderPage()
    expect(await screen.findByText('浦发银行')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('共 42 条')).toBeInTheDocument())
    expect(
      screen.getByRole('link', { name: /查看 浦发银行 sh\.600000 K线/ }),
    ).toBeInTheDocument()
  })
})
