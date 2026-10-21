import { FormEvent, useEffect, useState } from 'react'
import { ArrowRight, Command, LoaderCircle, LockKeyhole } from 'lucide-react'
import App from './App'

type User = { id: string; email: string; timezone: string; created_at: string }
type AuthMode = 'login' | 'register'

const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000'

async function request<T>(path: string, body?: Record<string, string>): Promise<T> {
  const response = await fetch(`${apiBase}/api/v1${path}`, {
    method: body ? 'POST' : 'GET',
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? 'Не удалось выполнить запрос. Попробуй ещё раз.')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export default function AuthGate() {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [invitation, setInvitation] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    void request<User>('/auth/me')
      .then((current) => { if (active) setUser(current) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setChecking(false) })
    return () => { active = false }
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const path = mode === 'login' ? '/auth/login' : '/auth/register'
      const payload = mode === 'login'
        ? { email, password }
        : { email, password, invitation_token: invitation.trim() }
      const current = await request<User>(path, payload)
      setUser(current)
      setPassword('')
      setInvitation('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось выполнить запрос.')
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    try {
      await request<void>('/auth/logout', {})
    } finally {
      setUser(null)
      setPassword('')
    }
  }

  if (checking) {
    return <div className="auth-loading"><LoaderCircle className="spin" size={24}/><span>Проверяем сессию…</span></div>
  }
  if (user) {
    return <div className="authenticated-app"><div className="auth-session"><span>Вошли как <b>{user.email}</b></span><button onClick={() => void logout()}>Выйти <ArrowRight size={14}/></button></div><App/></div>
  }

  return <main className="auth-screen">
    <section className="auth-card">
      <a className="brand auth-brand" href="#login"><span className="brand-mark"><Command size={20}/></span><span><strong>personal<span>OS</span></strong><small>YOUR LIFE, IN SYNC</small></span></a>
      <div className="auth-heading"><span className="auth-symbol"><LockKeyhole size={19}/></span><p className="date">ЛИЧНОЕ ПРОСТРАНСТВО</p><h1>{mode === 'login' ? 'С возвращением' : 'Создать аккаунт'}</h1><p>{mode === 'login' ? 'Войди, чтобы продолжить работу с Personal OS.' : 'Регистрация доступна только по персональному приглашению.'}</p></div>
      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <label>Email<input type="email" autoComplete="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com"/></label>
        <label>Пароль<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'register' ? 'Минимум 12 символов' : 'Твой пароль'}/></label>
        {mode === 'register' && <label>Код приглашения<input autoComplete="off" required minLength={32} maxLength={256} value={invitation} onChange={(event) => setInvitation(event.target.value)} placeholder="Вставь персональный токен"/></label>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="primary auth-submit" type="submit" disabled={busy}>{busy ? <><LoaderCircle size={16} className="spin"/> Подожди…</> : <>{mode === 'login' ? 'Войти' : 'Зарегистрироваться'} <ArrowRight size={16}/></>}</button>
      </form>
      <p className="auth-switch">{mode === 'login' ? 'Есть приглашение?' : 'Уже есть аккаунт?'} <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Создать аккаунт' : 'Войти'}</button></p>
      <p className="auth-note">Сессия хранится в защищённой cookie. Пароль и токен не сохраняются в браузерном хранилище.</p>
    </section>
  </main>
}
