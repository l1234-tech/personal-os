import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarDays, Check, ExternalLink, RefreshCw, ShieldCheck, Unplug } from 'lucide-react'
import { api, ApiError, type CalendarEvent, type GoogleCalendar, type Integration, type PersonalCalendarEvent } from './api'

function message(error: unknown) {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'Не удалось выполнить запрос.'
}
function localIso(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
export default function GoogleCalendarPanel() {
  const [integration, setIntegration] = useState<Integration | null>(null)
  const [calendars, setCalendars] = useState<GoogleCalendar[]>([])
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [personalEvents, setPersonalEvents] = useState<PersonalCalendarEvent[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [rangeStart] = useState(() => { const d = new Date(); d.setHours(0,0,0,0); return localIso(d) })
  const [rangeEnd] = useState(() => { const d = new Date(); d.setDate(d.getDate()+14); d.setHours(23,59,0,0); return localIso(d) })
  const load = useCallback(async () => {
    setBusy(true); setNotice('')
    try {
      const integrations = await api.integrations()
      const connected = integrations.find((item) => item.provider === 'google_calendar' && item.status === 'active') ?? null
      setIntegration(connected)
      if (!connected) { setCalendars([]); setEvents([]); setPersonalEvents([]); return }
      const list = await api.googleCalendars()
      setCalendars(list)
      setSelected(list.filter((item) => item.selected).map((item) => item.id))
      const start = new Date(rangeStart).toISOString()
      const end = new Date(rangeEnd).toISOString()
      const [googleEvents, ownEvents] = await Promise.all([api.calendarEvents(start, end), api.personalCalendarEvents(start, end)])
      setEvents(googleEvents)
      setPersonalEvents(ownEvents)
    } catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }, [rangeEnd, rangeStart])
  useEffect(() => { void load() }, [load])
  async function connect() {
    setBusy(true); setNotice('')
    try { const result = await api.connectGoogle(); window.location.assign(result.authorization_url) }
    catch (error) { setNotice(message(error)); setBusy(false) }
  }
  async function saveSelection() {
    setBusy(true); setNotice('')
    try { setCalendars(await api.saveGoogleCalendars(selected)); setNotice('Выбор календарей сохранён.') }
    catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }
  async function sync() {
    setBusy(true); setNotice('')
    try {
      const result = await api.syncGoogle()
      setNotice(`Синхронизация завершена: календарей ${result.calendars_synced}, просмотрено событий ${result.events_seen}, обновлено ${result.events_created_or_updated}.`)
      const start = new Date(rangeStart).toISOString()
      const end = new Date(rangeEnd).toISOString()
      setEvents(await api.calendarEvents(start, end))
    } catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }
  async function publish(event: PersonalCalendarEvent) {
    const target = event.google_calendar_id ?? selected[0]
    if (!target) { setNotice('Сначала выбери и сохрани календарь Google.'); return }
    setBusy(true); setNotice('')
    try {
      const saved = await api.publishCalendarEvent(event.id, target)
      setPersonalEvents((current) => current.map((item) => item.id === saved.id ? saved : item))
      setNotice('Событие опубликовано или обновлено в Google Calendar.')
    } catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }
  async function acceptGoogleVersion(event: PersonalCalendarEvent) {
    if (!window.confirm(`Заменить локальное событие «${event.title}» актуальной версией из Google Calendar? Локальные изменения будут потеряны.`)) return
    setBusy(true); setNotice('')
    try {
      const saved = await api.resolveCalendarEventFromGoogle(event.id)
      setPersonalEvents((current) => current.map((item) => item.id === saved.id ? saved : item))
      setNotice('Локальное событие обновлено версией из Google Calendar.')
    } catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }
  async function disconnect() {
    if (!window.confirm('Отключить Google Calendar и удалить сохранённые токены и синхронизированные события из Personal OS?')) return
    setBusy(true); setNotice('')
    try { await api.disconnectGoogle(); setIntegration(null); setCalendars([]); setEvents([]); setPersonalEvents([]); setSelected([]); setNotice('Google Calendar отключён.') }
    catch (error) { setNotice(message(error)) }
    finally { setBusy(false) }
  }
  const sortedEvents = useMemo(() => [...events].filter((event) => event.status !== 'cancelled').sort((a,b) => a.start_at.localeCompare(b.start_at)), [events])
  return <section className="area-page">
    <div className="welcome"><div><p className="date">ИНТЕГРАЦИИ</p><h1>Google Calendar</h1><p className="subtitle">Импорт событий Google и публикация личных событий Personal OS в выбранный календарь.</p></div><button className="secondary" onClick={() => void load()} disabled={busy}><RefreshCw size={15}/> Обновить</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <article className="panel calendar-connect-panel">
      <div className="calendar-connect-heading"><span className="module-icon"><CalendarDays size={20}/></span><div><h3>{integration ? 'Google-аккаунт подключён' : 'Подключи Google-аккаунт'}</h3><p>{integration ? `Статус: ${integration.status} · подключён ${new Date(integration.connected_at).toLocaleString('ru-RU')}` : 'Открой доступ к календарям, выбери нужные и синхронизируй события.'}</p></div><span className="calendar-connection-state">{integration ? <><Check size={14}/> Подключено</> : 'Не подключено'}</span></div>
      {!integration ? <button className="primary" onClick={() => void connect()} disabled={busy}>Подключить Google Calendar <ExternalLink size={15}/></button> : <div className="calendar-actions"><button className="primary" onClick={() => void sync()} disabled={busy || selected.length === 0}><RefreshCw size={15}/> Синхронизировать события</button><button className="quiet" onClick={() => void disconnect()} disabled={busy}><Unplug size={15}/> Отключить</button></div>}
      <p className="calendar-security"><ShieldCheck size={14}/> Токены хранятся на backend в зашифрованном виде. Запись запускается вручную; обновления проверяются по версии события, чтобы не затереть внешние изменения.</p>
    </article>
    {integration && <>
      <article className="panel"><div className="panel-title"><div><h3>Мои календари</h3><p>Отметь календари, события которых нужно импортировать.</p></div><button className="secondary" onClick={() => void saveSelection()} disabled={busy}>Сохранить выбор</button></div>
        <div className="calendar-list">{calendars.map((calendar) => <label className="calendar-choice" key={calendar.id}><input type="checkbox" checked={selected.includes(calendar.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, calendar.id] : current.filter((id) => id !== calendar.id))}/><span><b>{calendar.summary}</b><small>{calendar.primary ? 'Основной календарь' : calendar.access_role}</small></span>{calendar.primary && <em>Основной</em>}</label>)}{!calendars.length && <div className="empty">Список календарей пуст. Попробуй обновить данные.</div>}</div>
      </article>
      <article className="panel"><div className="panel-title"><div><h3>Мои события Personal OS</h3><p>Выбери календарь выше и опубликуй событие. Повторная публикация проверяет конфликты.</p></div><span className="duration">{personalEvents.length} событий</span></div>
        <div className="calendar-event-list">{personalEvents.map((event) => <div className="calendar-event-row" key={event.id}><time>{event.all_day ? 'Весь день' : new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(event.start_at))}</time><div><b>{event.title}</b><small>{event.sync_status === 'synced' ? 'Синхронизировано' : event.sync_status === 'conflict' ? 'Конфликт — требуется проверка' : event.sync_status === 'error' ? 'Ошибка отправки' : 'Только в Personal OS'}</small></div>{event.sync_status === 'conflict' ? <button className="secondary" onClick={() => void acceptGoogleVersion(event)} disabled={busy}>Принять версию Google</button> : <button className="secondary" onClick={() => void publish(event)} disabled={busy || selected.length === 0}>{event.google_event_id ? 'Обновить в Google' : 'Опубликовать'}</button>}</div>)}{!personalEvents.length && <div className="empty">Личных событий в этом диапазоне пока нет.</div>}</div>
      </article>
      <article className="panel"><div className="panel-title"><div><h3>Ближайшие события</h3><p>События на ближайшие 14 дней после последней синхронизации.</p></div><span className="duration">{sortedEvents.length} событий</span></div>
        <div className="calendar-event-list">{sortedEvents.map((event) => <div className="calendar-event-row" key={event.id}><time>{event.all_day ? 'Весь день' : new Intl.DateTimeFormat('ru-RU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(event.start_at))}</time><div><b>{event.title}</b><small>{event.all_day ? ' ' : new Intl.DateTimeFormat('ru-RU',{hour:'2-digit',minute:'2-digit'}).format(new Date(event.end_at))}{event.description ? ` · ${event.description.slice(0,180)}` : ''}</small></div>{event.html_link && <a href={event.html_link} target="_blank" rel="noreferrer" aria-label="Открыть событие в Google Calendar"><ExternalLink size={14}/></a>}</div>)}{!sortedEvents.length && <div className="empty"><CalendarDays size={20}/><b>Событий пока нет</b><span>Сохрани выбор календарей и запусти синхронизацию.</span></div>}</div>
      </article>
    </>}
  </section>
}
