import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { loginWithCredentials } from '../../services/api'
import Login from '../Login'

vi.mock('../../services/api', () => ({ loginWithCredentials: vi.fn() }))

const mockedLogin = vi.mocked(loginWithCredentials)

function renderLogin(entry = '/login') {
  return render(
    <MemoryRouter
      initialEntries={[entry]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Login />
    </MemoryRouter>,
  )
}

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear()
    mockedLogin.mockReset()
    mockedLogin.mockResolvedValue(undefined)
  })

  it('submits the account and password once without persisting them', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText('账号'), ' analyst ')
    await user.type(screen.getByLabelText('登录密码'), 'correct-horse')
    await user.click(screen.getByRole('button', { name: /进入量化系统/ }))

    expect(mockedLogin).toHaveBeenCalledWith('analyst', 'correct-horse')
    expect(localStorage.getItem('api_key')).toBeNull()
    expect(localStorage.getItem('password')).toBeNull()
  })

  it('shows a clear error when authentication fails', async () => {
    mockedLogin.mockRejectedValueOnce(new Error('invalid'))
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByLabelText('账号'), 'analyst')
    await user.type(screen.getByLabelText('登录密码'), 'wrong')
    await user.click(screen.getByRole('button', { name: /进入量化系统/ }))

    expect(await screen.findByText(/账号或密码不正确/)).toBeInTheDocument()
  })

  it('toggles password visibility', async () => {
    const user = userEvent.setup()
    renderLogin()

    const password = screen.getByLabelText('登录密码')
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: '显示密码' }))
    expect(password).toHaveAttribute('type', 'text')
    await user.click(screen.getByRole('button', { name: '隐藏密码' }))
    expect(password).toHaveAttribute('type', 'password')
  })

  it('keeps unavailable entry points disabled', () => {
    renderLogin()

    expect(screen.getByRole('button', { name: /注册账号/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /企业协作登录/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /微信快捷授权/ })).toBeDisabled()
  })

  it('links back to the welcome page', () => {
    renderLogin()

    expect(screen.getByRole('link', { name: /了解 Backing/ })).toHaveAttribute(
      'href',
      '/welcome/',
    )
  })
})
