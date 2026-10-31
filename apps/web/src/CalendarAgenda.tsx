import { useCallback, useEffect, useState } from 'react'
import { CalendarDays, Clock3, RefreshCw } from 'lucide-react'
import { api, type CalendarEvent, type PersonalCalendarEvent, type TaskBlock } from './api'

type AgendaItem = {
  id: string
  title: string
  start: string
  end: string
  source: 'google' | 'personal' | 'task'
}

function localDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

export default function CalendarAgenda() {
  const [items, setItems] = useState<AgendaItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(end.getDate() + 14)
    try {
      const from = start.toISOString()
      const to = end.toISOString()
      const [google, personal, blocks] = await Promise.all([
        api.calendarEvents(from, to),
        api.personalCalendarEvents(from, to),
        api.taskBlocks(from, to),
      ])
      const next: AgendaItem[] = [
        ...google.filter((event: CalendarEvent) => event.status !== 'cancelled').map((event) => ({
          id: `google:${event.id}`, title: event.title, start: event.start_at, end: event.end_at, source: 'google' as const,
        })),
        ...personal.map((event: PersonalCalendarEvent) => ({
          id: `personal:${event.id}`, title: event.title, start: event.start_at, end: event.end_at, source: 'personal' as const,
        })),
        ...blocks.map((block: TaskBlock) => ({
          id: `task:${block.id}`, title: block.title, start: block.start_at, end: block.end_at, source: 'task' as const,
        })),
      ]
      setItems(next.sort((a, b) => a.start.localeCompare(b.start)).slice(0, 12))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить календарь')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  return <section className="calendar-agenda panel" aria-label="Ближайшие события">
    <div className="calendar-agenda-heading">
      <div><h3><CalendarDays size={16}/> Ближайшие события</h3><p>Единое расписание на 14 дней: Google, Personal OS и задачи</p></div>
      <button className="quiet" onClick={() => void load()} disabled={loading} aria-label="Обновить календарь"><RefreshCw size={15}/></button>
    </div>
    {error && <p className="calendar-agenda-error" role="status">{error}</p>}
    {!items.length && !loading && !error && <p className="calendar-agenda-empty">На ближайшие 14 дней событий нет.</p>}
    {loading && !items.length && <p className="calendar-agenda-empty">Загружаю расписание…</p>}
    <div className="calendar-agenda-list">
      {items.map((item) => <div className="calendar-agenda-item" key={item.id}>
        <time>{localDate(item.start)}</time><span className={`calendar-agenda-source ${item.source}`}>{item.source === 'google' ? 'Google' : item.source === 'personal' ? 'Личное' : 'Задача'}</span>
        <b>{item.title}</b><small><Clock3 size={12}/>{new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(item.start))}–{new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(item.end))}</small>
      </div>)}
    </div>
  </section>
}
