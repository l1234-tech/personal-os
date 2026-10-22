import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowRight, Bell, BookOpen, CalendarDays, Check, ChevronDown, Clock3, Command, Compass, GraduationCap, LayoutDashboard, ListTodo, LogOut, Plus, Search, Settings2, Sparkles, Timer, UsersRound, Wallet, Zap, AlertCircle, RefreshCw } from 'lucide-react'
import AuthScreen from './AuthScreen'
import { api, ApiError, type ApiTask, type TaskPriority, type TimeEntry, type TimerState, type User } from './api'

const groups = [
  { title: 'РАБОЧЕЕ ПРОСТРАНСТВО', items: [{ label: 'Обзор дня', icon: LayoutDashboard }, { label: 'Планировщик', icon: CalendarDays }, { label: 'Задачи', icon: ListTodo }, { label: 'Фокус и время', icon: Timer }] },
  { title: 'НАПРАВЛЕНИЯ', items: [{ label: 'Учёба', icon: GraduationCap }, { label: 'ML и проекты', icon: Compass }, { label: 'Репетиторство', icon: UsersRound }, { label: 'Финансы', icon: Wallet }] },
]
const areaColors: Record<string, string> = { itmo: 'violet', study: 'violet', education: 'violet', ml: 'blue', project: 'blue', tutoring: 'amber', personal: 'violet' }
function categoryColor(category: string) {
  const normalized = category.toLowerCase()
  const key = Object.keys(areaColors).find((item) => normalized.includes(item))
  return key ? areaColors[key] : 'violet'
}
function formatDuration(minutes: number | null) {
  if (!minutes) return 'Без оценки'
  return minutes < 60 ? `${minutes} мин` : `${Math.floor(minutes / 60)} ч${minutes % 60 ? ` ${minutes % 60} мин` : ''}`
}
function localDateTimeValue(date = new Date()) { const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return local.toISOString().slice(0, 16) }
function formatClock(seconds: number) {
  return [Math.floor(seconds / 3600), Math.floor(seconds % 3600 / 60), seconds % 60].map((part) => String(part).padStart(2, '0')).join(':')
}
function apiMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Сессия завершена. Войди снова.'
    if (error.status === 0) return 'Не удалось связаться с сервером. Проверь, запущен ли backend.'
    if (error.status === 409) return error.message || 'Операция конфликтует с текущим состоянием.'
    if (error.status === 422) return error.message || 'Проверь поля формы.'
    return error.message
  }
  return error instanceof Error ? error.message : 'Не удалось выполнить операцию.'
}
export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authResolved, setAuthResolved] = useState(false)
  const [tasks, setTasks] = useState<ApiTask[]>([])
  const [timeEntries, setTimeEntries] = useState<TimeEntry[]>([])
  const [manualCategory, setManualCategory] = useState('study')
  const [manualNotes, setManualNotes] = useState('')
  const [manualStart, setManualStart] = useState(() => localDateTimeValue(new Date(Date.now() - 60 * 60 * 1000)))
  const [manualEnd, setManualEnd] = useState(() => localDateTimeValue())
  const [savingEntry, setSavingEntry] = useState(false)
  const [activePage, setActivePage] = useState('Обзор дня')
  const [query, setQuery] = useState('')
  const [draft, setDraft] = useState('')
  const [category, setCategory] = useState('personal')
  const [priority, setPriority] = useState<TaskPriority>('medium')
  const [estimatedMinutes, setEstimatedMinutes] = useState('45')
  const [composer, setComposer] = useState(false)
  const [timer, setTimer] = useState<TimerState | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [loading, setLoading] = useState(false)
  const [savingTask, setSavingTask] = useState(false)
  const [timerBusy, setTimerBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState<'all' | 'open' | 'done'>('open')
  const [online, setOnline] = useState(navigator.onLine)
  const refreshWorkspace = useCallback(async () => {
    setLoading(true)
    try {
      const [loadedTasks, loadedTimer, loadedEntries] = await Promise.all([api.tasks(), api.currentTimer(), api.timeEntries()])
      setTasks(loadedTasks)
      setTimer(loadedTimer)
      setTimeEntries(loadedEntries)
      setSeconds(loadedTimer?.elapsed_seconds ?? 0)
      setNotice('')
    } catch (error) {
      setNotice(apiMessage(error))
      if (error instanceof ApiError && error.status === 401) {
        setUser(null)
        setTasks([])
        setTimer(null)
      }
    } finally {
      setLoading(false)
      setAuthResolved(true)
    }
  }, [])
  useEffect(() => {
    let cancelled = false
    api.me().then((currentUser) => { if (!cancelled) setUser(currentUser) })
      .catch(() => { if (!cancelled) setUser(null) })
      .finally(() => { if (!cancelled) setAuthResolved(true) })
    const onlineHandler = () => setOnline(true)
    const offlineHandler = () => setOnline(false)
    window.addEventListener('online', onlineHandler)
    window.addEventListener('offline', offlineHandler)
    return () => {
      cancelled = true
      window.removeEventListener('online', onlineHandler)
      window.removeEventListener('offline', offlineHandler)
    }
  }, [])
  useEffect(() => { if (user) void refreshWorkspace() }, [user, refreshWorkspace])
  useEffect(() => {
    if (!timer || timer.status !== 'running') return
    const startedAt = Date.now()
    const base = timer.elapsed_seconds
    const tick = () => setSeconds(base + Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    tick()
    const interval = window.setInterval(tick, 1000)
    return () => window.clearInterval(interval)
  }, [timer?.id, timer?.status, timer?.elapsed_seconds])
  const done = tasks.filter((task) => task.status === 'done').length
  const visible = useMemo(() => tasks.filter((task) => {
    const matchesQuery = `${task.title} ${task.description ?? ''} ${task.category}`.toLowerCase().includes(query.toLowerCase())
    const matchesFilter = filter === 'all' || (filter === 'done' ? task.status === 'done' : task.status !== 'done' && task.status !== 'cancelled')
    return matchesQuery && matchesFilter
  }), [tasks, query, filter])
  const dateLabel = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  const timeLabel = formatClock(seconds)
  const openTasks = tasks.filter((task) => task.status !== 'done' && task.status !== 'cancelled')
  async function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = draft.trim()
    if (!title) return
    setSavingTask(true); setNotice('')
    try {
      const parsedEstimate = estimatedMinutes.trim() ? Number(estimatedMinutes) : undefined
      if (parsedEstimate !== undefined && (!Number.isInteger(parsedEstimate) || parsedEstimate <= 0)) {
        setNotice('Оценка времени должна быть положительным целым числом минут.')
        return
      }
      const task = await api.createTask({ title, category, priority, ...(parsedEstimate !== undefined ? { estimated_minutes: parsedEstimate } : {}) })
      setTasks((current) => [task, ...current]); setDraft(''); setComposer(false)
    } catch (error) { setNotice(apiMessage(error)) }
    finally { setSavingTask(false) }
  }
  async function addManualEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const startedAt = new Date(manualStart)
    const endedAt = new Date(manualEnd)
    if (!manualStart || !manualEnd || Number.isNaN(startedAt.getTime()) || Number.isNaN(endedAt.getTime()) || endedAt <= startedAt) {
      setNotice('Время окончания должно быть позже времени начала.')
      return
    }
    setSavingEntry(true)
    setNotice('')
    try {
      const entry = await api.createTimeEntry({
        category: manualCategory.trim(),
        notes: manualNotes.trim() || undefined,
        started_at: startedAt.toISOString(),
        ended_at: endedAt.toISOString(),
        source: 'manual',
      })
      setTimeEntries((current) => [entry, ...current])
      setManualNotes('')
      setNotice('Запись времени сохранена.')
    } catch (error) { setNotice(apiMessage(error)) }
    finally { setSavingEntry(false) }
  }
  async function toggleTask(task: ApiTask) {
    setNotice('')
    try {
      const updated = await api.updateTask(task.id, { status: task.status === 'done' ? 'todo' : 'done' })
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (error) { setNotice(apiMessage(error)) }
  }
  async function changeTimerAction(action: 'start' | 'pause' | 'resume' | 'stop') {
    setTimerBusy(true); setNotice('')
    try {
      let next: TimerState
      if (action === 'start') next = await api.startTimer(category)
      else if (action === 'pause') next = await api.pauseTimer()
      else if (action === 'resume') next = await api.resumeTimer()
      else next = await api.stopTimer()
      if (action === 'stop') {
        setTimer(null); setSeconds(0); setTasks(await api.tasks()); setTimeEntries(await api.timeEntries())
        setNotice('Фокус-сессия сохранена в фактическом времени.')
      } else { setTimer(next); setSeconds(next.elapsed_seconds) }
    } catch (error) {
      setNotice(apiMessage(error))
      if (error instanceof ApiError && error.status === 409) {
        try { const current = await api.currentTimer(); setTimer(current); setSeconds(current?.elapsed_seconds ?? 0) }
        catch { /* Keep the original actionable error. */ }
      }
    } finally { setTimerBusy(false) }
  }
  async function logout() {
    try { await api.logout() } catch { /* Session may already be expired. */ }
    setUser(null); setTasks([]); setTimeEntries([]); setTimer(null); setSeconds(0); setNotice('')
  }
  if (!authResolved) return <div className="initial-loading"><span className="loading-mark"><Command size={22} /></span><p>Открываю личное пространство…</p></div>
  if (!user) return <AuthScreen onAuthenticated={setUser} />
  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="#home"><span className="brand-mark"><Command size={20}/></span><span><strong>personal<span>OS</span></strong><small>YOUR LIFE, IN SYNC</small></span></a>
      <button className="workspace"><span className="workspace-mark">P</span><span><b>Моё пространство</b><small>Personal workspace</small></span><ChevronDown size={15}/></button>
      <nav>{groups.map((group) => <div className="nav-group" key={group.title}><p>{group.title}</p>{group.items.map(({ label, icon: Icon }) => <button key={label} className={activePage === label ? 'nav-link active' : 'nav-link'} onClick={() => setActivePage(label)}><Icon size={17}/><span>{label}</span>{label === 'Задачи' && <em>{openTasks.length}</em>}</button>)}</div>)}</nav>
      <div className="side-bottom"><div className="sync"><i className={online ? 'online-dot' : 'offline-dot'}/> <span><b>{online ? 'Подключение активно' : 'Нет сети'}</b><small>{loading ? 'Синхронизация…' : 'Данные из личного API'}</small></span></div><button className="nav-link" onClick={() => setActivePage('Настройки')}><Settings2 size={17}/><span>Настройки</span></button><div className="profile"><div>{user.email.slice(0, 1).toUpperCase()}</div><span><b>{user.email}</b><small>Личный аккаунт</small></span><button className="quiet logout-button" onClick={() => void logout()} title="Выйти" aria-label="Выйти"><LogOut size={15}/></button></div></div>
    </aside>
    <main id="home" className="main">
      <header className="topbar"><div className="crumb"><span>Рабочее пространство</span><ArrowRight size={13}/><b>{activePage}</b></div><div className="top-actions"><label className="search"><Search size={15}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по задачам..."/><kbd>⌘ K</kbd></label><button className="icon-button" aria-label="Уведомления"><Bell size={18}/></button><div className="avatar">{user.email.slice(0, 1).toUpperCase()}</div></div></header>
      <div className="content">
        <section className="welcome"><div><p className="date">{dateLabel}</p><h1>Личное пространство <span>✳</span></h1><p className="subtitle">Планы становятся результатами. Сегодня — только реальные данные.</p></div><button className="primary" onClick={() => setComposer(true)}><Plus size={17}/> Новая задача</button></section>
        {!online && <div className="notice offline-notice"><AlertCircle size={16}/> Нет соединения. Изменения не сохраняются офлайн; дождись сети и повтори действие.</div>}
        {notice && <div className="notice" role="status"><AlertCircle size={16}/><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Закрыть сообщение">×</button></div>}
        {activePage === 'Настройки' ? <section className="panel module-placeholder"><div className="module-icon"><Settings2 size={20}/></div><p className="date-label">АККАУНТ</p><h1>Настройки пространства</h1><p>Ты вошёл как <b>{user.email}</b>. Сейчас доступна базовая сессия; настройки интеграций и уведомлений будут подключены отдельными этапами.</p><button className="secondary" onClick={() => void refreshWorkspace()}><RefreshCw size={15}/> Обновить данные</button></section> : activePage === 'Фокус и время' ? <section className="time-page">
          <div className="welcome"><div><p className="date">УЧЁТ ФАКТИЧЕСКОЙ РАБОТЫ</p><h1>Фокус и время</h1><p className="subtitle">Записывай время по факту и сравнивай его с оценками задач.</p></div><button className="secondary" onClick={() => void refreshWorkspace()}><RefreshCw size={15}/> Обновить</button></div>
          <div className="time-summary">
            <article className="panel"><span>Записей времени</span><strong>{timeEntries.length}</strong></article>
            <article className="panel"><span>Учтено времени</span><strong>{formatClock(timeEntries.reduce((sum, entry) => sum + entry.duration_seconds, 0))}</strong></article>
            <article className="panel"><span>Таймер сейчас</span><strong>{timer ? formatClock(seconds) : 'Не запущен'}</strong></article>
          </div>
          <article className="panel"><div className="panel-title"><div><h3>Добавить прошедшую сессию</h3><p>Например, учёба, разработка или занятие с учеником.</p></div></div>
            <form className="manual-entry-form" onSubmit={(event) => void addManualEntry(event)}>
              <label>Направление<input value={manualCategory} onChange={(event) => setManualCategory(event.target.value)} required maxLength={64} placeholder="study, ml, tutoring…" /></label>
              <div className="manual-dates"><label>Начало<input type="datetime-local" value={manualStart} onChange={(event) => setManualStart(event.target.value)} required /></label><label>Окончание<input type="datetime-local" value={manualEnd} onChange={(event) => setManualEnd(event.target.value)} required /></label></div>
              <label>Заметка<textarea value={manualNotes} onChange={(event) => setManualNotes(event.target.value)} maxLength={10000} rows={2} placeholder="Что именно делал?" /></label>
              <button className="primary" type="submit" disabled={savingEntry || !online}>{savingEntry ? 'Сохраняю…' : <><Plus size={15}/> Сохранить время</>}</button>
            </form>
          </article>
          <article className="panel"><div className="panel-title"><div><h3>История времени</h3><p>Последние {timeEntries.length} записей</p></div></div>
            <div className="entry-list">{timeEntries.map((entry) => <div className="entry-row" key={entry.id}><div className={'marker ' + categoryColor(entry.category)} /><div className="task-copy"><b>{entry.category}</b><span>{new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(entry.started_at))} — {new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(entry.ended_at))}{entry.notes ? ' · ' + entry.notes : ''}</span></div><span className="duration">{formatClock(entry.duration_seconds)}</span></div>)}
              {!timeEntries.length && <div className="empty"><Clock3 size={20}/><b>Записей пока нет</b><span>Добавь первую ручную запись или заверши фокус-сессию таймером.</span></div>}
            </div>
          </article>
        </section> :
        <><section className="hero-grid">
          <article className="focus-card"><div className="orb orb-a"/><div className="orb orb-b"/><div className="card-top"><span className="pill"><Sparkles size={13}/> ФОКУС ДНЯ</span><span className="draft-label">{loading ? 'Синхронизация…' : 'Из базы данных'}</span></div><div className="focus-copy"><p>ТВОЯ ГЛАВНАЯ ЦЕЛЬ</p><h2>{openTasks.length ? 'Сделать важное.' : 'Время выбрать следующий шаг.'}<br/>{openTasks.length ? 'Не просто заняться делами.' : 'Не обязательно всё сразу.'}</h2><span>{openTasks.length ? 'Начни с одной задачи, которая сдвинет тебя вперёд. Отмечай факт выполнения — план должен опираться на реальность.' : 'Добавь задачу или проверь свои цели. Отдых тоже часть устойчивого плана.'}</span></div><div className="focus-bottom"><div><small>Завершение задач</small><div className="progress"><span style={{width: `${tasks.length ? done / tasks.length * 100 : 0}%`}}/></div></div><b>{done}/{tasks.length}</b><button className="round-arrow" aria-label="К задачам" onClick={() => setActivePage('Задачи')}><ArrowRight size={16}/></button></div></article>
          <article className="timer-card"><div className="timer-top"><span className="timer-icon"><Timer size={17}/></span><span>Фокус-сессия</span><span className="quiet" title="Состояние хранится на сервере"><Clock3 size={16}/></span></div><p className="timer-label">ТЕКУЩАЯ СЕССИЯ</p><div className="timer-value">{timeLabel}</div><div className="timer-state"><i className={timer?.status === 'running' ? 'live' : ''}/>{timer?.status === 'running' ? 'Таймер запущен' : timer?.status === 'paused' ? 'Таймер на паузе' : 'Готов к фокусировке'}</div><div className="timer-bottom">{!timer ? <button className="primary" disabled={timerBusy || !online} onClick={() => void changeTimerAction('start')}><Zap size={15}/> Начать фокус</button> : timer.status === 'running' ? <button className="secondary" disabled={timerBusy || !online} onClick={() => void changeTimerAction('pause')}>Пауза</button> : <button className="primary" disabled={timerBusy || !online} onClick={() => void changeTimerAction('resume')}><Zap size={15}/> Продолжить</button>}{timer && <button className="stop-button" disabled={timerBusy || !online} onClick={() => void changeTimerAction('stop')}>Завершить</button>}<span>{timer ? 'Запись сохранится в фактическом времени' : 'Без активной сессии'}</span></div></article>
        </section>
        <section className="stats-grid"><article className="stat"><div className="stat-top"><span>Незавершённые задачи</span><i className="violet"><ListTodo size={16}/></i></div><div className="stat-number">{openTasks.length}<small> / {tasks.length}</small></div><div className="stat-foot"><b>{done} завершено</b><span>из личного списка</span></div></article><article className="stat"><div className="stat-top"><span>Время в фокусе</span><i className="blue"><Clock3 size={16}/></i></div><div className="stat-number">{Math.floor(seconds / 3600)}<small> ч </small>{Math.floor(seconds % 3600 / 60)}<small> мин</small></div><div className="stat-foot"><span>{timer ? (timer.status === 'paused' ? 'Пауза' : 'Активная сессия') : 'Текущая сессия'}</span><span>{timer?.status === 'running' ? '●' : '—'}</span></div></article><article className="stat"><div className="stat-top"><span>Главные направления</span><i className="amber"><BookOpen size={16}/></i></div><div className="tags"><span>ITMO</span><span>ML / DS</span><span>Репетиторство</span></div><div className="stat-foot"><span>Баланс по результатам</span><span>4 области</span></div></article></section>
        <section className="lower-grid"><article className="panel"><div className="panel-title"><div><h3>{activePage === 'Задачи' ? 'Все задачи' : 'Приоритеты дня'}</h3><p>{loading ? 'Загружаю данные из API…' : 'Задачи загружены из личного пространства'}</p></div><button className="link-button" onClick={() => setActivePage(activePage === 'Задачи' ? 'Обзор дня' : 'Задачи')}>{activePage === 'Задачи' ? 'Обзор дня' : 'Все задачи'} <ArrowRight size={14}/></button></div>
          {composer && <form className="composer" onSubmit={(event) => void addTask(event)}><input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Что нужно сделать?" aria-label="Название новой задачи" maxLength={200} required/><select aria-label="Категория" value={category} onChange={(event) => setCategory(event.target.value)}><option value="personal">Личное</option><option value="itmo">ITMO / Учёба</option><option value="ml">ML / DS</option><option value="tutoring">Репетиторство</option><option value="project">Проект</option></select><select aria-label="Приоритет" value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)}><option value="low">Низкий</option><option value="medium">Обычный</option><option value="high">Высокий</option><option value="urgent">Срочный</option></select><input aria-label="Оценка времени в минутах" type="number" min="1" max="100000" value={estimatedMinutes} onChange={(event) => setEstimatedMinutes(event.target.value)} placeholder="Минуты" /><button className="primary" type="submit" disabled={savingTask || !online}>{savingTask ? 'Сохраняю…' : <><Plus size={15}/> Добавить</>}</button><button type="button" className="quiet" onClick={() => setComposer(false)}>Отмена</button></form>}
          <div className="task-filters"><button className={filter === 'open' ? 'selected' : ''} onClick={() => setFilter('open')}>Активные</button><button className={filter === 'all' ? 'selected' : ''} onClick={() => setFilter('all')}>Все</button><button className={filter === 'done' ? 'selected' : ''} onClick={() => setFilter('done')}>Завершённые</button></div>
          <div className="task-list">{visible.map((task) => <div className={'task-row ' + (task.status === 'done' ? 'is-done' : '')} key={task.id}><button className={'check ' + (task.status === 'done' ? 'checked' : '')} aria-label={task.status === 'done' ? 'Вернуть в работу' : 'Отметить выполненной'} disabled={!online} onClick={() => void toggleTask(task)}>{task.status === 'done' && <Check size={13}/>}</button><div className={'marker ' + categoryColor(task.category)}/><div className="task-copy"><b>{task.title}</b><span>{task.category} · {task.priority === 'urgent' ? 'срочно' : task.priority === 'high' ? 'высокий приоритет' : task.priority === 'low' ? 'низкий приоритет' : 'обычный приоритет'}{task.due_at ? ` · срок ${new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(task.due_at))}` : ''}</span></div><span className="duration">{formatDuration(task.estimated_minutes)}</span></div>)}{!visible.length && <div className="empty"><ListTodo size={20}/><b>{query ? 'Ничего не найдено' : filter === 'done' ? 'Пока нет завершённых задач' : 'Список пока пуст'}</b><span>{query ? 'Попробуй изменить поисковый запрос.' : 'Добавь первую задачу — она сохранится в базе и появится здесь после входа с другого устройства.'}</span></div>}</div><button className="add-link" onClick={() => setComposer(true)}><Plus size={15}/> Добавить задачу в список</button></article>
          <article className="panel"><div className="panel-title"><div><h3>Планирование дня</h3><p>План и факт разделяются</p></div><button className="quiet" aria-label="Обновить состояние" onClick={() => void refreshWorkspace()}><RefreshCw size={16}/></button></div><div className="calendar-empty"><span className="calendar-empty-icon"><CalendarDays size={18}/></span><b>Календарь ещё не подключён</b><p>Пока не показываю вымышленные события. На следующем этапе появятся Google Calendar, конфликты, дедлайны и подтверждение изменений плана.</p><div className="calendar-status"><i/> Ожидает подключения Google Calendar</div></div><div className="schedule-note"><Clock3 size={15}/><span>Только таймер или ручная запись создают факт времени. Задача и событие календаря сами по себе не считаются работой.</span></div></article></section></>}
        <footer className="footer"><span>PERSONAL OS <b>·</b> API-INTEGRATED BUILD</span><span><i className={online ? 'online-dot' : 'offline-dot'}/> {online ? 'Состояние синхронизируется с backend' : 'Офлайн · изменения не отправляются'}</span></footer>
      </div>
    </main>
  </div>
}
