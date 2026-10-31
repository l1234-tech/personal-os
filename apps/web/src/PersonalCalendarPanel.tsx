import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronLeft, ChevronRight, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { api, ApiError, type PersonalCalendarEvent } from './api'

type View = 'day' | 'week' | 'month'
const colors: PersonalCalendarEvent['color'][] = ['blue', 'violet', 'green', 'amber', 'rose', 'gray']
const pad = (value: number) => String(value).padStart(2, '0')
const toLocalInput = (date: Date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate())
const addDays = (date: Date, amount: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + amount)
const startOfWeek = (date: Date) => {
  const day = startOfDay(date)
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7))
  return day
}
const iso = (date: Date) => date.toISOString()
const dateLabel = (date: Date, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' }) =>
  new Intl.DateTimeFormat('ru-RU', options).format(date)
const timeLabel = (date: string) => new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(date))
const apiError = (error: unknown) => error instanceof ApiError ? error.message : 'Не удалось выполнить запрос'

export default function PersonalCalendarPanel() {
  const [view, setView] = useState<View>('week')
  const [cursor, setCursor] = useState(() => new Date())
  const [events, setEvents] = useState<PersonalCalendarEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<PersonalCalendarEvent | null>(null)
  const [composer, setComposer] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [color, setColor] = useState<PersonalCalendarEvent['color']>('blue')
  const [saving, setSaving] = useState(false)

  const range = useMemo(() => {
    if (view === 'day') return { start: startOfDay(cursor), end: addDays(startOfDay(cursor), 1) }
    if (view === 'week') {
      const start = startOfWeek(cursor)
      return { start, end: addDays(start, 7) }
    }
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1)
    const start = startOfWeek(first)
    return { start, end: addDays(start, 42) }
  }, [cursor, view])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setEvents(await api.personalCalendarEvents(iso(range.start), iso(range.end)))
    } catch (err) {
      setError(apiError(err))
    } finally {
      setLoading(false)
    }
  }, [range.start.getTime(), range.end.getTime()])

  useEffect(() => { void load() }, [load])

  const openNew = (date: Date) => {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 10, 0)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    setEditing(null)
    setTitle('')
    setDescription('')
    setStartAt(toLocalInput(start))
    setEndAt(toLocalInput(end))
    setColor('blue')
    setComposer(true)
  }
  const openEdit = (event: PersonalCalendarEvent) => {
    setEditing(event)
    setTitle(event.title)
    setDescription(event.description ?? '')
    setStartAt(toLocalInput(new Date(event.start_at)))
    setEndAt(toLocalInput(new Date(event.end_at)))
    setColor(event.color)
    setComposer(true)
  }
  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !startAt || !endAt || new Date(endAt) <= new Date(startAt)) {
      setError('Проверь название и время события.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = { title: title.trim(), description: description.trim() || null, start_at: new Date(startAt).toISOString(), end_at: new Date(endAt).toISOString(), color }
      if (editing) await api.updateCalendarEvent(editing.id, payload)
      else await api.createCalendarEvent(payload)
      setComposer(false)
      await load()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setSaving(false)
    }
  }
  const remove = async () => {
    if (!editing || !window.confirm('Удалить это событие?')) return
    setSaving(true)
    try {
      await api.deleteCalendarEvent(editing.id)
      setComposer(false)
      await load()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setSaving(false)
    }
  }

  const days = useMemo(() => {
    const count = view === 'month' ? 42 : view === 'week' ? 7 : 1
    return Array.from({ length: count }, (_, index) => addDays(range.start, index))
  }, [range.start.getTime(), view])
  const titleLabel = view === 'day'
    ? dateLabel(cursor, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    : view === 'week'
      ? `${dateLabel(range.start)} — ${dateLabel(addDays(range.end, -1), { day: 'numeric', month: 'long', year: 'numeric' })}`
      : new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' }).format(cursor)

  const move = (direction: number) => {
    if (view === 'day') setCursor(addDays(cursor, direction))
    else if (view === 'week') setCursor(addDays(cursor, direction * 7))
    else setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1))
  }

  return <section className="personal-calendar">
    <div className="calendar-toolbar">
      <div className="calendar-nav">
        <button className="secondary" onClick={() => move(-1)} aria-label="Предыдущий период"><ChevronLeft size={16}/></button>
        <button className="secondary" onClick={() => setCursor(new Date())}>Сегодня</button>
        <button className="secondary" onClick={() => move(1)} aria-label="Следующий период"><ChevronRight size={16}/></button>
        <h2>{titleLabel}</h2>
      </div>
      <div className="calendar-actions">
        <div className="calendar-views">{(['day', 'week', 'month'] as View[]).map((item) => <button key={item} className={view === item ? 'selected' : ''} onClick={() => setView(item)}>{item === 'day' ? 'День' : item === 'week' ? 'Неделя' : 'Месяц'}</button>)}</div>
        <button className="secondary" onClick={() => void load()} disabled={loading}><RefreshCw size={14}/></button>
        <button className="primary" onClick={() => openNew(cursor)}><Plus size={15}/> Событие</button>
      </div>
    </div>
    {error && <div className="notice" role="alert">{error}</div>}
    {loading && <p className="calendar-loading">Обновляю календарь…</p>}
    <div className={`personal-calendar-grid ${view}`}>
      {view !== 'day' && ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'].map((day) => <div className="calendar-weekday" key={day}>{day}</div>)}
      {days.map((day) => {
        const dayEvents = events.filter((event) => new Date(event.start_at) < addDays(day, 1) && new Date(event.end_at) > day)
        return <div className={`calendar-day ${day.getMonth() !== cursor.getMonth() && view === 'month' ? 'muted-day' : ''}`} key={day.toISOString()}>
          <button className="calendar-day-number" onClick={() => { setCursor(day); if (view === 'month') setView('day') }}>{view === 'day' ? dateLabel(day, { weekday: 'long', day: 'numeric', month: 'long' }) : day.getDate()}</button>
          <div className="calendar-day-events">
            {dayEvents.map((event) => <button key={event.id} className={`calendar-event-chip ${event.color}`} onClick={() => openEdit(event)} title={`${event.title} · ${timeLabel(event.start_at)}–${timeLabel(event.end_at)}`}>
              {view !== 'month' && <time>{timeLabel(event.start_at)}</time>}{event.title}
            </button>)}
            <button className="calendar-add-slot" onClick={() => openNew(day)} aria-label={`Добавить событие: ${dateLabel(day)}`}>+</button>
          </div>
        </div>
      })}
    </div>
    {!events.length && !loading && <div className="calendar-empty-state">Пока нет событий. Нажми на дату или «Событие», чтобы добавить первое.</div>}
    {composer && <div className="calendar-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setComposer(false) }}>
      <form className="calendar-event-form" onSubmit={(event) => void save(event)}>
        <div className="calendar-form-heading"><div><span>{editing ? 'ИЗМЕНЕНИЕ' : 'НОВОЕ СОБЫТИЕ'}</span><h3>{editing ? 'Редактировать событие' : 'Создать событие'}</h3></div><button type="button" className="quiet" onClick={() => setComposer(false)} aria-label="Закрыть"><X size={18}/></button></div>
        <label>Название<input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={500} autoFocus placeholder="Например, занятие или встреча"/></label>
        <label>Описание<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} maxLength={10000} placeholder="Дополнительная информация"/></label>
        <div className="calendar-form-times"><label>Начало<input type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} required/></label><label>Окончание<input type="datetime-local" value={endAt} onChange={(event) => setEndAt(event.target.value)} required/></label></div>
        <label>Цвет <div className="calendar-color-picker">{colors.map((item) => <button key={item} type="button" className={`color-dot ${item} ${color === item ? 'active' : ''}`} onClick={() => setColor(item)} aria-label={item}/>)}</div></label>
        <div className="calendar-form-actions">{editing && <button type="button" className="quiet danger" onClick={() => void remove()} disabled={saving}><Trash2 size={15}/> Удалить</button>}<button type="button" className="secondary" onClick={() => setComposer(false)}>Отмена</button><button type="submit" className="primary" disabled={saving}>{saving ? 'Сохраняю…' : 'Сохранить'}</button></div>
      </form>
    </div>}
  </section>
}
