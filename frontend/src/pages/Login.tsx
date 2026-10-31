import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { loginWithCredentials } from '../services/api'
import { safeNextPath } from '../utils/nextPath'

const FEATURES = [
  {
    code: '01_ALPHA',
    tag: '多因子',
    tone: 'mint',
    title: '策略研究',
    body: '内置趋势、反转与突破策略，参数网格优化与因子拆解，信号到净值曲线全部可复现。',
    metricLabel: 'STRATEGIES',
    metric: '13 个内置策略',
  },
  {
    code: '02_SIMULATE',
    tag: '回测就绪',
    tone: 'blue',
    title: '回测与归因',
    body: '同一引擎服务页面与 API，逐笔成交、费用、回撤与持仓曲线完整落库。',
    metricLabel: 'ENGINE',
    metric: '单一执行引擎',
  },
  {
    code: '03_RADAR',
    tag: 'AI 研判',
    tone: 'lavender',
    title: 'AI 研究与模拟盘',
    body: '工具网关约束下的多智能体研究，模拟盘审批、T+1 撮合与复盘归因。',
    metricLabel: 'PAPER',
    metric: 'T+1 撮合',
  },
] as const

const INDICES = [
  { name: '上证指数 (000001.SH)', value: '3,088.42', change: '+1.24%' },
  { name: '沪深300 (000300.SH)', value: '3,592.10', change: '+0.88%' },
] as const

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  )
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
      {off && <path d="M4 20 20 4" />}
    </svg>
  )
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" />
      <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
    </svg>
  )
}

/**
 * 登录页：账号 + 密码换取短期 HttpOnly session cookie。
 *
 * 密码只在本次请求中出现（内存态），随后即被丢弃——不写入 localStorage、
 * 不进入 bundle、不随后续请求发送。
 */
export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const params = new URLSearchParams(location.search)
  const nextFromQuery = safeNextPath(params.get('next'))
  const nextFromState = safeNextPath(
    (location.state as { from?: string } | null)?.from ?? null,
  )
  const from = nextFromQuery || nextFromState || '/'

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return
    const account = username.trim()
    if (!account || !password) {
      setError('请输入账号和密码')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await loginWithCredentials(account, password)
      navigate(from, { replace: true })
    } catch {
      setError('登录失败：账号或密码不正确，或服务不可用，请检查后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-frame">
        <header className="login-strip">
          <div className="login-strip__brand">
            <span className="login-strip__pulse" aria-hidden="true" />
            <span className="login-strip__name">BACKING QUANT v1.0</span>
            <span className="login-strip__slash" aria-hidden="true">
              /
            </span>
            <span className="login-strip__tier">RESEARCH TIER</span>
          </div>
          <div className="login-strip__meta">
            <span className="login-strip__health">
              <span className="login-strip__dot" aria-hidden="true" />
              SESSION · HTTPONLY
            </span>
            <span className="login-strip__sep" aria-hidden="true">
              |
            </span>
            <span className="login-strip__hide-sm">CSRF DOUBLE-SUBMIT</span>
            <span className="login-strip__chip">A 股研究工作台</span>
          </div>
        </header>

        <div className="login-layout">
          <section className="login-hero" aria-labelledby="login-hero-title">
            <div className="login-hero__badge">
              <span className="login-hero__badge-strong">A股研究</span>
              <span className="login-hero__badge-sep">·</span>
              <span>研究与模拟交易版</span>
              <span className="login-hero__badge-dot" aria-hidden="true" />
              <span className="login-hero__badge-version">Backing Core</span>
            </div>

            <h1 id="login-hero-title" className="login-hero__title">
              量化决策系统
            </h1>
            <p className="login-hero__subtitle">A 股研究、回测与模拟交易工作台</p>
            <p className="login-hero__lede">
              策略研究、回测引擎与 AI
              研判共用一套可复现的数据与工具网关，从信号到净值曲线全部可追溯。
            </p>

            <ul className="login-features">
              {FEATURES.map((feature) => (
                <li className="login-feature" key={feature.code}>
                  <div className="login-feature__head">
                    <span className="login-feature__code">{feature.code}</span>
                    <span
                      className={`login-feature__tag login-feature__tag--${feature.tone}`}
                    >
                      {feature.tag}
                    </span>
                  </div>
                  <h2 className="login-feature__title">{feature.title}</h2>
                  <p className="login-feature__body">{feature.body}</p>
                  <div className="login-feature__foot">
                    <span className="login-feature__metric-label">
                      {feature.metricLabel}
                    </span>
                    <span className="login-feature__metric">{feature.metric}</span>
                  </div>
                </li>
              ))}
            </ul>

            <div className="login-telemetry">
              <div className="login-telemetry__head">
                <span className="login-telemetry__title">
                  MARKET SNAPSHOT
                  <span className="login-telemetry__live" aria-hidden="true" />
                </span>
                <span className="login-telemetry__note">示例快照 · 非实时</span>
              </div>
              <div className="login-telemetry__grid">
                {INDICES.map((index) => (
                  <div className="login-telemetry__cell" key={index.name}>
                    <span className="login-telemetry__name">{index.name}</span>
                    <span className="login-telemetry__value-row">
                      <span className="login-telemetry__value">{index.value}</span>
                      <span className="login-telemetry__change">{index.change}</span>
                    </span>
                  </div>
                ))}
                <div className="login-telemetry__cell">
                  <span className="login-telemetry__name">综合研判信号</span>
                  <span className="login-telemetry__value-row">
                    <span className="login-telemetry__signal">积极看多 BULLISH</span>
                    <span className="login-telemetry__conf">CONF 91%</span>
                  </span>
                </div>
              </div>
              <ul className="login-trust">
                <li>HttpOnly 会话</li>
                <li>CSRF 双重校验</li>
                <li>密码不落盘</li>
              </ul>
            </div>
          </section>

          <aside className="login-panel">
            <div className="login-panel__head">
              <div>
                <h2 className="login-panel__title">欢迎使用量化系统</h2>
                <p className="login-panel__hint">请使用管理员分配的账号登录研究终端</p>
              </div>
              <span className="login-panel__chip">ACCOUNT AUTH</span>
            </div>

            <div className="login-tabs" role="group" aria-label="登录方式">
              <button
                type="button"
                className="login-tab login-tab--active"
                aria-pressed="true"
              >
                账号登录
              </button>
              <button
                type="button"
                className="login-tab"
                aria-pressed="false"
                disabled
                title="即将开放"
              >
                注册账号
              </button>
            </div>

            <form className="login-form" onSubmit={onSubmit} noValidate>
              <div className="login-form__bar">
                <span className="login-form__eyebrow">AUTH CREDENTIALS</span>
                <span className="login-form__bar-note">管理员分配</span>
              </div>

              <div className="login-field">
                <label className="login-field__label" htmlFor="login-username">
                  账号
                </label>
                <div className="login-field__control">
                  <input
                    id="login-username"
                    name="username"
                    type="text"
                    className="login-input"
                    placeholder="请输入账号"
                    autoComplete="username"
                    autoFocus
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                  />
                  <span className="login-field__icon">
                    <UserIcon />
                  </span>
                </div>
              </div>

              <div className="login-field">
                <div className="login-field__row">
                  <label className="login-field__label" htmlFor="login-password">
                    登录密码
                  </label>
                </div>
                <div className="login-field__control">
                  <input
                    id="login-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    className="login-input login-input--password"
                    placeholder="请输入密码"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <button
                    type="button"
                    className="login-eye"
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    <EyeIcon off={showPassword} />
                  </button>
                </div>
              </div>

              {error && (
                <p className="login-error" role="alert">
                  {error}
                </p>
              )}

              <div className="login-form__meta">
                <span className="login-form__session">会话有效期 8 小时</span>
                <span className="login-form__secure">
                  <LockIcon />
                  PBKDF2 校验
                </span>
              </div>

              <button type="submit" className="login-submit" disabled={submitting}>
                {submitting ? (
                  <>
                    <span className="login-spinner" aria-hidden="true" />
                    核验安全凭证…
                  </>
                ) : (
                  <>
                    进入量化系统
                    <span className="login-submit__arrow" aria-hidden="true">
                      →
                    </span>
                  </>
                )}
              </button>
            </form>

            <div className="login-panel__sso">
              <div className="login-panel__sso-head">
                <span className="login-form__eyebrow">ENTERPRISE / FAST CONNECT</span>
                <span className="login-panel__sso-note">即将开放</span>
              </div>
              <div className="login-panel__sso-grid">
                <button type="button" className="login-sso" disabled title="即将开放">
                  企业协作登录
                </button>
                <button type="button" className="login-sso" disabled title="即将开放">
                  微信快捷授权
                </button>
              </div>
            </div>

            <div className="login-panel__foot">
              <Link to="/welcome/" className="login-panel__welcome">
                了解 Backing
              </Link>
              <span>SESSION 8H · SECURE ENCLAVE</span>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
