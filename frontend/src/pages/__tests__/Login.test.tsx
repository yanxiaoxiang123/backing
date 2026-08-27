import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { loginWithApiKey } from '../../services/api'
import Login from '../Login'

vi.mock('../../services/api', () => ({ loginWithApiKey: vi.fn() }))

const mockedLogin = vi.mocked(loginWithApiKey)

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear()
    mockedLogin.mockReset()
    mockedLogin.mockResolvedValue(undefined)
  })

  it('submits the API key once and does not persist it in the form', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Login />
      </MemoryRouter>,
    )

    const input = screen.getByPlaceholderText('API Key')
    await user.type(input, ' secret-key ')
    await user.click(screen.getByRole('button', { name: /登\s*录/ }))

    expect(mockedLogin).toHaveBeenCalledWith('secret-key')
    expect(localStorage.getItem('api_key')).toBeNull()
  })

  it('shows a clear error when authentication fails', async () => {
    mockedLogin.mockRejectedValueOnce(new Error('invalid'))
    const user = userEvent.setup()
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Login />
      </MemoryRouter>,
    )

    await user.type(screen.getByPlaceholderText('API Key'), 'bad-key')
    await user.click(screen.getByRole('button', { name: /登\s*录/ }))
    expect(await screen.findByText(/API Key 无效/)).toBeInTheDocument()
  })
})
