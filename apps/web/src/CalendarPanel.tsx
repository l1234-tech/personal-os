import { useCallback, useEffect, useState } from "react"
import { AlertCircle, CalendarDays, Check, ExternalLink, Link2, RefreshCw, Unplug } from "lucide-react"
import { api, type CalendarEvent, type GoogleCalendar, type Integration } from "./api"

function localDateTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "short", day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(value))
}

export default function CalendarPanel() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [calendars, setCalendars] = useState<GoogleCalendar[]>([])
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  const connected = integrations.some(item => item.provider === "google_calendar" && item.status === "active")

  const refresh = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const current = await api.integrations()
      setIntegrations(current)
      if (current.some(item => item.provider === "google_calendar" && item.status === "active")) {
        const available = await api.googleCalendars()
        setCalendars(available)
        setSelectedIds(available.filter(calendar => calendar.selected).map(calendar => calendar.id))
        const start = new Date()
        start.setHours(0, 0, 0, 0)
        const end = new Date(start)
        end.setDate(end.getDate() + 7)
        setEvents(await api.calendarEvents(start.toISOString(), end.toISOString()))
      } else {
        setCalendars([])
        setEvents([])
        setSelectedIds([])
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось загрузить настройки календаря")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  async function connect() {
    setBusy(true)
    setError("")
    try {
      const result = await api.connectGoogleCalendar()
      window.location.assign(result.authorization_url)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось начать Google OAuth")
      setBusy(false)
    }
  }

  async function saveSelection() {
    setBusy(true)
    setError("")
    setMessage("")
    try {
      const saved = await api.selectGoogleCalendars(selectedIds)
      setCalendars(saved)
      setSelectedIds(saved.filter(calendar => calendar.selected).map(calendar => calendar.id))
      setMessage("Выбор календарей сохранён.")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить выбор")
    } finally {
      setBusy(false)
    }
  }

  async function sync() {
    setBusy(true)
    setError("")
    setMessage("")
    try {
      const result = await api.syncGoogleCalendar()
      await refresh()
      setMessage(`Синхронизация завершена: ${result.calendars_synced} календарей, ${result.events_seen} событий обработано.`)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Синхронизация не завершилась")
    } finally {
      setBusy(false)
    }
  }

  async function disconnect() {
    if (!window.confirm("Отключить Google Calendar и удалить сохранённые у Personal OS токены?")) return
    setBusy(true)
    setError("")
    try {
      await api.disconnectGoogleCalendar()
      setMessage("Google Calendar отключён.")
      await refresh()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отключить календарь")
    } finally {
      setBusy(false)
    }
  }

  return <section className="calendar-page">
    <div className="calendar-page-heading">
      <div>
        <p className="date-label">PLANNING &amp; SCHEDULE</p>
        <h1>Планировщик</h1>
        <p className="calendar-page-subtitle">Сначала читаем реальные события. Блоки задач публикуются в календарь только после явного подтверждения.</p>
      </div>
      <span className={connected ? "calendar-connection-state connected" : "calendar-connection-state"}>
        <i /> {connected ? "Google подключён" : "Google не подключён"}
      </span>
    </div>

    {error && <div className="calendar-feedback error" role="alert"><AlertCircle size={16}/><span>{error}</span></div>}
    {message && <div className="calendar-feedback success" role="status"><Check size={16}/><span>{message}</span></div>}

    <article className="panel calendar-connection-card">
      <div className="calendar-card-icon"><CalendarDays size={22}/></div>
      <div className="calendar-card-main">
        <h3>Google Calendar</h3>
        <p>{connected ? "Выбери календари, события которых нужно синхронизировать." : "Подключение использует OAuth. Если серверные credentials не настроены, API вернёт понятную ошибку; приложение не подменяет её демо-событиями."}</p>
        {!connected
          ? <button className="primary calendar-action" onClick={() => { void connect() }} disabled={busy || loading}><Link2 size={15}/> Подключить Google</button>
          : <div className="calendar-actions">
              <button className="primary calendar-action" onClick={() => { void sync() }} disabled={busy || loading || selectedIds.length === 0}><RefreshCw size={15}/> Синхронизировать</button>
              <button className="secondary calendar-action" onClick={() => { void refresh() }} disabled={busy || loading}><RefreshCw size={15}/> Обновить</button>
              <button className="danger-quiet" onClick={() => { void disconnect() }} disabled={busy}><Unplug size={15}/> Отключить</button>
            </div>
        }
      </div>
    </article>

    {connected && <div className="calendar-settings-grid">
      <article className="panel calendar-selection-panel">
        <div className="panel-title"><div><h3>Календари</h3><p>Отметь источники событий</p></div><span className="count-pill">{selectedIds.length} выбрано</span></div>
        {loading ? <p className="calendar-empty-note">Загружаю список календарей…</p> : calendars.length === 0 ? <p className="calendar-empty-note">Список пуст. Проверь доступ Google и попробуй обновить.</p> :
          <div className="calendar-selection-list">{calendars.map(calendar => <label key={calendar.id} className="calendar-select-row">
            <input type="checkbox" checked={selectedIds.includes(calendar.id)} disabled={busy}
              onChange={event => setSelectedIds(current => event.target.checked
                ? [...current, calendar.id]
                : current.filter(id => id !== calendar.id))}/>
            <span className="calendar-select-copy"><b>{calendar.summary}</b><small>{calendar.primary ? "Основной календарь" : calendar.access_role}</small></span>
          </label>)}</div>}
        {connected && <button className="primary calendar-save-button" onClick={() => { void saveSelection() }} disabled={busy || loading}>{busy ? "Сохраняю…" : "Сохранить выбор"}</button>}
      </article>

      <article className="panel calendar-events-panel">
        <div className="panel-title"><div><h3>Ближайшие 7 дней</h3><p>События, сохранённые из Google Calendar</p></div><span className="count-pill">{events.length}</span></div>
        {!events.length ? <div className="calendar-event-empty"><CalendarDays size={22}/><b>Пока нет синхронизированных событий</b><span>Выбери календари и запусти синхронизацию.</span></div> :
          <div className="calendar-event-list">{events.map(event => <div className="calendar-event-row" key={event.id}>
            <i/>
            <div><b>{event.title}</b><span>{localDateTime(event.start_at)} – {new Intl.DateTimeFormat("ru-RU",{hour:"2-digit",minute:"2-digit"}).format(new Date(event.end_at))}</span></div>
            {event.html_link && <a href={event.html_link} target="_blank" rel="noreferrer" aria-label="Открыть событие в Google Calendar"><ExternalLink size={14}/></a>}
          </div>)}</div>
        }
      </article>
    </div>}

    <div className="calendar-safety-note"><AlertCircle size={15}/><span>Personal OS не изменяет существующие внешние события. Создание блоков задач и публикация — разные действия; конфликт требует разрешения до публикации.</span></div>
    {loading && <p className="calendar-loading-note">Обновление состояния интеграции…</p>}
  </section>
}
