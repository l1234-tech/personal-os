import { FormEvent, useState } from "react"
import { ArrowRight, Command, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react"
import { api, User } from "./api"

type Props = {
  onAuthenticated: (user: User) => void
}

export default function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [invitationToken, setInvitationToken] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setBusy(true)
    try {
      const normalizedEmail = email.trim().toLowerCase()
      const user = mode === "login"
        ? await api.login(normalizedEmail, password)
        : await api.register(normalizedEmail, password, invitationToken.trim())
      onAuthenticated(user)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить запрос")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell">
      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />
      <section className="auth-card">
        <a className="auth-brand" href="#auth" aria-label="Personal OS">
          <span className="auth-brand-icon"><Command size={22} /></span>
          <span><strong>personal<span>OS</span></strong><small>YOUR LIFE, IN SYNC</small></span>
        </a>
        <div className="auth-intro">
          <span className="auth-kicker"><ShieldCheck size={14} /> ЛИЧНОЕ ПРОСТРАНСТВО</span>
          <h1>{mode === "login" ? "Собери день в систему." : "Начни своё пространство."}</h1>
          <p>{mode === "login"
            ? "Войди, чтобы продолжить работу с задачами, временем и целями."
            : "Регистрация закрытая: нужен одноразовый код приглашения."}</p>
        </div>
        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            <span>Email</span>
            <input
              autoComplete="email"
              inputMode="email"
              type="email"
              required
              maxLength={320}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </label>
          <label>
            <span>Пароль</span>
            <input
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              type="password"
              minLength={mode === "register" ? 12 : 1}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={mode === "register" ? "Не менее 12 символов" : "Твой пароль"}
            />
          </label>
          {mode === "register" && <label>
            <span>Код приглашения</span>
            <input
              autoComplete="off"
              type="password"
              minLength={32}
              required
              value={invitationToken}
              onChange={(event) => setInvitationToken(event.target.value)}
              placeholder="Вставь одноразовый токен"
            />
          </label>}
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Проверяю..." : mode === "login" ? "Войти в Personal OS" : "Создать аккаунт"}
            {!busy && <ArrowRight size={16} />}
          </button>
        </form>
        <div className="auth-switch">
          {mode === "login" ? "Нет аккаунта с приглашением?" : "Уже есть аккаунт?"}
          <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError("") }}>
            {mode === "login" ? "Регистрация" : "Войти"}
          </button>
        </div>
        <div className="auth-security"><LockKeyhole size={14} /><span>Сессия хранится в защищённой HttpOnly-cookie. Доступ закрыт без авторизации.</span><KeyRound size={14} /></div>
      </section>
      <footer className="auth-footer">PERSONAL OS <span>·</span> PRIVATE BY DESIGN</footer>
    </main>
  )
}
