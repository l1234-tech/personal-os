import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronLeft, ChevronRight, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { api, ApiError, type ApiTask, type CalendarEvent, type PersonalCalendarEvent, type TaskBlock } from './api'

type View = 'day' | 'week' | 'month'
const colors: PersonalCalendarEvent['color'][] = ['blue', 'violet', 'green', 'amber', 'rose', 'gray']
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
  const [googleEvents, setGoogleEvents] = useState<CalendarEvent[]>([])
  const [tasks, setTasks] = useState<ApiTask[]>([])
  const [taskBlocks, setTaskBlocks] = useState<TaskBlock[]>([])
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [editingTaskBlock, setEditingTaskBlock] = useState<TaskBlock | null>(null)
  const [scheduleTaskId, setScheduleTaskId] = useState('')
  const [scheduleStart, setScheduleStart] = useState('')
  const [scheduleEnd, setScheduleEnd] = useState('')
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
  const [draggingEventId, setDraggingEventId] = useState<string | null>(null)
  const [draggingTaskBlockId, setDraggingTaskBlockId] = useState<string | null>(null)
  const [resizing, setResizing] = useState<{ id: string; startY: number; duration: number; nextDuration: number } | null>(null)
  const [resizingTaskBlock, setResizingTaskBlock] = useState<{ id: string; startY: number; duration: number; nextDuration: number } | null>(null)

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
      const [loadedEvents, loadedGoogleEvents, loadedTasks, loadedBlocks] = await Promise.all([api.personalCalendarEvents(iso(range.start), iso(range.end)), api.calendarEvents(iso(range.start), iso(range.end)), api.tasks(), api.taskBlocks(iso(range.start), iso(range.end))])
      setEvents(loadedEvents)
      setGoogleEvents(loadedGoogleEvents.filter((event) => event.status !== 'cancelled'))
      setTasks(loadedTasks)
      setTaskBlocks(loadedBlocks)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setLoading(false)
    }
  }, [range.start, range.end])

  useEffect(() => { void load() }, [load])

  const openNew = (date: Date, hour = 10, minute = 0) => {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hour, minute)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    setEditing(null)
    setTitle('')
    setDescription('')
    setStartAt(toLocalInput(start))
    setEndAt(toLocalInput(end))
    setColor('blue')
    setComposer(true)
  }
  const openSchedule = () => {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate(), 10, 0)
    const end = new Date(start.getTime() + 60 * 60 * 1000)
    setEditingTaskBlock(null)
    setScheduleTaskId(tasks.find((task) => task.status !== 'done' && task.status !== 'cancelled')?.id ?? '')
    setScheduleStart(toLocalInput(start))
    setScheduleEnd(toLocalInput(end))
    setScheduleOpen(true)
  }
  const openTaskBlock = (block: TaskBlock) => {
    setEditingTaskBlock(block)
    setScheduleTaskId(block.task_id)
    setScheduleStart(toLocalInput(new Date(block.start_at)))
    setScheduleEnd(toLocalInput(new Date(block.end_at)))
    setScheduleOpen(true)
  }
  const saveTaskBlock = async (event: FormEvent) => {
    event.preventDefault()
    if (!scheduleTaskId || !scheduleStart || !scheduleEnd || new Date(scheduleEnd) <= new Date(scheduleStart)) {
      setError('Выбери задачу и корректный временной интервал.')
      return
    }
    setSaving(true)
    try {
      const interval = { start_at: new Date(scheduleStart).toISOString(), end_at: new Date(scheduleEnd).toISOString() }
      if (editingTaskBlock) await api.updateTaskBlock(editingTaskBlock.id, interval)
      else await api.createTaskBlock({ task_id: scheduleTaskId, ...interval })
      setScheduleOpen(false)
      setEditingTaskBlock(null)
      await load()
    } catch (err) { setError(apiError(err)) } finally { setSaving(false) }
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

  const moveEventToSlot = async (eventId: string, day: Date, hour: number) => {
    const event = events.find((item) => item.id === eventId)
    if (!event) return
    const originalStart = new Date(event.start_at)
    const originalEnd = new Date(event.end_at)
    const duration = originalEnd.getTime() - originalStart.getTime()
    const nextStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, 0)
    const nextEnd = new Date(nextStart.getTime() + duration)
    setDraggingEventId(null)
    try {
      await api.updateCalendarEvent(eventId, {
        start_at: nextStart.toISOString(),
        end_at: nextEnd.toISOString(),
      })
      await load()
    } catch (err) {
      setError(apiError(err))
    }
  }

  const moveTaskBlockToSlot = async (blockId: string, day: Date, hour: number) => {
    const block = taskBlocks.find((item) => item.id === blockId)
    if (!block) return
    const duration = new Date(block.end_at).getTime() - new Date(block.start_at).getTime()
    const nextStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, 0)
    setDraggingTaskBlockId(null)
    try {
      await api.updateTaskBlock(blockId, { start_at: nextStart.toISOString(), end_at: new Date(nextStart.getTime() + duration).toISOString() })
      await load()
    } catch (err) { setError(apiError(err)) }
  }

  const removeTaskBlock = async (block: TaskBlock) => {
    if (!window.confirm(`Убрать запланированный блок «${block.title}»?`)) return
    setSaving(true)
    try {
      await api.deleteTaskBlock(block.id)
      await load()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setSaving(false)
    }
  }

  const finishTaskBlockResize = async () => {
    if (!resizingTaskBlock) return
    const block = taskBlocks.find((item) => item.id === resizingTaskBlock.id)
    const nextDuration = Math.max(15 * 60 * 1000, resizingTaskBlock.nextDuration)
    setResizingTaskBlock(null)
    if (!block || nextDuration === resizingTaskBlock.duration) return
    try {
      await api.updateTaskBlock(block.id, {
        end_at: new Date(new Date(block.start_at).getTime() + nextDuration).toISOString(),
      })
      await load()
    } catch (err) {
      setError(apiError(err))
    }
  }

  const finishResize = async () => {
    if (!resizing) return
    const event = events.find((item) => item.id === resizing.id)
    const nextDuration = Math.max(15 * 60 * 1000, resizing.nextDuration)
    setResizing(null)
    if (!event || nextDuration === resizing.duration) return
    try {
      await api.updateCalendarEvent(event.id, {
        end_at: new Date(new Date(event.start_at).getTime() + nextDuration).toISOString(),
      })
      await load()
    } catch (err) {
      setError(apiError(err))
    }
  }

  const days = useMemo(() => {
    const count = view === 'month' ? 42 : view === 'week' ? 7 : 1
    return Array.from({ length: count }, (_, index) => addDays(range.start, index))
  }, [range.start, view])
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
        <button className="secondary" onClick={openSchedule}>Запланировать задачу</button><button className="primary" onClick={() => openNew(cursor)}><Plus size={15}/> Событие</button>
      </div>
    </div>
    {error && <div className="notice" role="alert">{error}</div>}
    {loading && <p className="calendar-loading">Обновляю календарь…</p>}
    {view === 'month' ? <div className="personal-calendar-grid month">
      {['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'].map((day) => <div className="calendar-weekday" key={day}>{day}</div>)}
      {days.map((day) => {
        const dayEvents = events.filter((event) => new Date(event.start_at) < addDays(day, 1) && new Date(event.end_at) > day)
        const dayGoogleEvents = googleEvents.filter((event) => new Date(event.start_at) < addDays(day, 1) && new Date(event.end_at) > day)
        const dueTasks = tasks.filter((task) => task.due_at && task.status !== 'done' && task.status !== 'cancelled' && new Date(task.due_at) >= day && new Date(task.due_at) < addDays(day, 1))
        const dayBlocks = taskBlocks.filter((block) => new Date(block.start_at) < addDays(day, 1) && new Date(block.end_at) > day)
        return <div className={`calendar-day ${day.getMonth() !== cursor.getMonth() ? 'muted-day' : ''}`} key={day.toISOString()}>
          <button className="calendar-day-number" onClick={() => { setCursor(day); setView('day') }}>{day.getDate()}</button>
          <div className="calendar-day-events">
            {dayEvents.slice(0, 3).map((event) => <button key={event.id} className={`calendar-event-chip ${event.color}`} onClick={() => openEdit(event)} title={`${event.title} · ${timeLabel(event.start_at)}–${timeLabel(event.end_at)}`}>{timeLabel(event.start_at)} {event.title}</button>)}
            {dayEvents.length > 3 && <span className="calendar-more">ещё {dayEvents.length - 3}</span>}
            {dayGoogleEvents.slice(0, 2).map((event) => <span key={event.id} className="calendar-event-chip google" title={event.title}>G · {event.all_day ? 'Весь день' : timeLabel(event.start_at)} {event.title}</span>)}
            {dayBlocks.slice(0, 2).map((block) => <span className="calendar-task-scheduled" key={block.id} title={`Запланировано: ${timeLabel(block.start_at)}–${timeLabel(block.end_at)}`}>▦ {timeLabel(block.start_at)} {tasks.find((task) => task.id === block.task_id)?.title ?? block.title}</span>)}
            {dayBlocks.length > 2 && <span className="calendar-more">ещё {dayBlocks.length - 2} блока</span>}
            {dueTasks.slice(0, 2).map((task) => <span className="calendar-task-deadline" key={task.id} title={`Срок: ${task.title}`}>◆ {task.title}</span>)}
            <button className="calendar-add-slot" onClick={() => openNew(day)} aria-label={`Добавить событие: ${dateLabel(day)}`}>+</button>
          </div>
        </div>
      })}
    </div> : <div className={`calendar-time-grid ${view}`}>
      <div className="calendar-time-head"><div className="calendar-time-gutter" />{days.map((day) => <button key={day.toISOString()} onClick={() => { setCursor(day); if (view === 'week') setView('day') }}>{dateLabel(day, { weekday: 'short', day: 'numeric' })}</button>)}</div>
      <div className="calendar-time-body">
        <div className="calendar-hour-labels">{Array.from({ length: 24 }, (_, hour) => <div key={hour}>{String(hour).padStart(2, '0')}:00</div>)}</div>
        {days.map((day) => {
          const dayEvents = events.filter((event) => new Date(event.start_at) < addDays(day, 1) && new Date(event.end_at) > day)
          const dueTasks = tasks.filter((task) => task.due_at && task.status !== 'done' && task.status !== 'cancelled' && new Date(task.due_at) >= day && new Date(task.due_at) < addDays(day, 1))
          return <div className="calendar-time-column" key={day.toISOString()}>
            {Array.from({ length: 24 }, (_, hour) => <button
              key={hour}
              className="calendar-time-slot"
              aria-label={`Создать событие ${dateLabel(day)} ${hour}:00`}
              onClick={() => openNew(day, hour, 0)}
              onDragOver={(event) => { if (draggingEventId || draggingTaskBlockId) event.preventDefault() }}
              onDrop={(event) => {
                event.preventDefault()
                if (draggingEventId) void moveEventToSlot(draggingEventId, day, hour)
                else if (draggingTaskBlockId) void moveTaskBlockToSlot(draggingTaskBlockId, day, hour)
              }}
            />)}
            {taskBlocks.filter((block) => new Date(block.start_at) < addDays(day, 1) && new Date(block.end_at) > day).map((block) => {
              const blockStart = new Date(block.start_at)
              const blockEnd = new Date(block.end_at)
              const blockStartMinutes = blockStart < day ? 0 : blockStart.getHours() * 60 + blockStart.getMinutes()
              const blockEndMinutes = blockEnd > addDays(day, 1) ? 1440 : blockEnd.getHours() * 60 + blockEnd.getMinutes()
              return <div key={block.id} className="calendar-task-block" style={{ top: blockStartMinutes / 60 * 52, height: Math.max(24, (resizingTaskBlock?.id === block.id ? resizingTaskBlock.nextDuration / 60000 : blockEndMinutes - blockStartMinutes) / 60 * 52) }} title={`Нажми, чтобы изменить время · перетащи, чтобы перенести · ${block.title}`} role="button" tabIndex={0} onClick={() => openTaskBlock(block)} onKeyDown={(keyEvent) => { if (keyEvent.key === 'Enter' || keyEvent.key === ' ') { keyEvent.preventDefault(); openTaskBlock(block) } }} draggable
                onDragStart={(dragEvent) => { dragEvent.dataTransfer.effectAllowed = 'move'; dragEvent.dataTransfer.setData('text/plain', block.id); setDraggingTaskBlockId(block.id) }}
                onDragEnd={() => setDraggingTaskBlockId(null)}>
                <b>{tasks.find((task) => task.id === block.task_id)?.title ?? block.title}</b><span>{timeLabel(block.start_at)}–{timeLabel(block.end_at)}</span><span className="calendar-task-block-resize-handle" aria-hidden="true"
                  onClick={(clickEvent) => clickEvent.stopPropagation()}
                  onPointerDown={(pointerEvent) => { pointerEvent.stopPropagation(); pointerEvent.preventDefault(); pointerEvent.currentTarget.setPointerCapture(pointerEvent.pointerId); setResizingTaskBlock({ id: block.id, startY: pointerEvent.clientY, duration: blockEnd.getTime() - blockStart.getTime(), nextDuration: blockEnd.getTime() - blockStart.getTime() }) }}
                  onPointerMove={(pointerEvent) => { if (!resizingTaskBlock || resizingTaskBlock.id !== block.id) return; const delta = (pointerEvent.clientY - resizingTaskBlock.startY) * 60 / 52 * 60000; setResizingTaskBlock({ ...resizingTaskBlock, nextDuration: Math.max(15 * 60000, resizingTaskBlock.duration + delta) }) }}
                  onPointerUp={() => { void finishTaskBlockResize() }}
                  onPointerCancel={() => setResizingTaskBlock(null)} />
                <button type="button" className="calendar-task-block-edit" aria-label={`Изменить время: ${block.title}`} title="Изменить время" onClick={(clickEvent) => { clickEvent.stopPropagation(); openTaskBlock(block) }}>↗</button><button type="button" className="calendar-task-block-remove" aria-label={`Удалить блок: ${block.title}`} title="Убрать из календаря" onClick={(clickEvent) => { clickEvent.stopPropagation(); void removeTaskBlock(block) }}>×</button>
              </div>
            })}
            {dueTasks.map((task) => {
              const due = new Date(task.due_at as string)
              const top = (due.getHours() * 60 + due.getMinutes()) / 60 * 52
              return <div key={task.id} className="calendar-deadline-line" style={{ top }} title={`Дедлайн: ${task.title}`}><span>{timeLabel(task.due_at as string)}</span><b>{task.title}</b></div>
            })}
            {googleEvents.filter((event) => new Date(event.start_at) < addDays(day, 1) && new Date(event.end_at) > day).map((event) => {
              const start = new Date(event.start_at)
              const end = new Date(event.end_at)
              const startMinutes = start < day ? 0 : start.getHours() * 60 + start.getMinutes()
              const endMinutes = end > addDays(day, 1) ? 1440 : end.getHours() * 60 + end.getMinutes()
              return <div key={event.id} className="calendar-timed-event google" style={{ top: startMinutes / 60 * 52, height: Math.max(25, (endMinutes - startMinutes) / 60 * 52) }} title={`Google Calendar · ${event.title}`}>
                <b>{event.title}</b><span>{event.all_day ? 'Весь день' : `${timeLabel(event.start_at)}–${timeLabel(event.end_at)}`}</span>
              </div>
            })}
            {dayEvents.map((event) => {
              const start = new Date(event.start_at)
              const end = new Date(event.end_at)
              const startMinutes = start < day ? 0 : start.getHours() * 60 + start.getMinutes()
              const endMinutes = end > addDays(day, 1) ? 1440 : end.getHours() * 60 + end.getMinutes()
              const top = startMinutes / 60 * 52
              const duration = (resizing?.id === event.id ? resizing.nextDuration / 60000 : endMinutes - startMinutes)
              const height = Math.max(25, duration / 60 * 52)
              return <button
                key={event.id}
                className={`calendar-timed-event ${event.color}`}
                style={{ top, height }}
                draggable
                onDragStart={(dragEvent) => {
                  dragEvent.dataTransfer.effectAllowed = 'move'
                  dragEvent.dataTransfer.setData('text/plain', event.id)
                  setDraggingEventId(event.id)
                }}
                onDragEnd={() => setDraggingEventId(null)}
                onClick={() => openEdit(event)}
                title={`Перетащи, чтобы перенести · ${event.title} · ${timeLabel(event.start_at)}–${timeLabel(event.end_at)}`}
              >
                <b>{event.title}</b><span>{timeLabel(event.start_at)}–{timeLabel(event.end_at)}</span>
                <span
                  className="calendar-event-resize-handle"
                  aria-hidden="true"
                  onClick={(clickEvent) => clickEvent.stopPropagation()}
                  onPointerDown={(pointerEvent) => {
                    pointerEvent.stopPropagation()
                    pointerEvent.preventDefault()
                    pointerEvent.currentTarget.setPointerCapture(pointerEvent.pointerId)
                    setResizing({
                      id: event.id,
                      startY: pointerEvent.clientY,
                      duration: end.getTime() - start.getTime(),
                      nextDuration: end.getTime() - start.getTime(),
                    })
                  }}
                  onPointerMove={(pointerEvent) => {
                    if (!resizing || resizing.id !== event.id) return
                    const delta = (pointerEvent.clientY - resizing.startY) * 60 / 52 * 60000
                    setResizing({ ...resizing, nextDuration: Math.max(15 * 60000, resizing.duration + delta) })
                  }}
                  onPointerUp={() => { void finishResize() }}
                  onPointerCancel={() => { setResizing(null) }}
                />
              </button>
            })}
          </div>
        })}
      </div>
    </div>}
    {!events.length && !googleEvents.length && !loading && <div className="calendar-empty-state">Пока нет событий. Нажми на дату или «Событие», чтобы добавить первое.</div>}
    {scheduleOpen && <div className="calendar-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setScheduleOpen(false) }}>
      <form className="calendar-event-form" onSubmit={(event) => void saveTaskBlock(event)}>
        <div className="calendar-form-heading"><div><span>ПЛАНИРОВАНИЕ</span><h3>{editingTaskBlock ? 'Изменить время задачи' : 'Запланировать задачу'}</h3></div><button type="button" className="quiet" onClick={() => setScheduleOpen(false)} aria-label="Закрыть"><X size={18}/></button></div>
        {!editingTaskBlock && <label>Задача<select value={scheduleTaskId} onChange={(event) => setScheduleTaskId(event.target.value)} required><option value="">Выбери задачу</option>{tasks.filter((task) => task.status !== 'done' && task.status !== 'cancelled').map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>}
        <div className="calendar-form-times"><label>Начало<input type="datetime-local" value={scheduleStart} onChange={(event) => setScheduleStart(event.target.value)} required/></label><label>Окончание<input type="datetime-local" value={scheduleEnd} onChange={(event) => setScheduleEnd(event.target.value)} required/></label></div>
        <div className="calendar-form-actions"><button type="button" className="secondary" onClick={() => setScheduleOpen(false)}>Отмена</button><button type="submit" className="primary" disabled={saving || !tasks.some((task) => task.id === scheduleTaskId)}>{saving ? 'Сохраняю…' : editingTaskBlock ? 'Сохранить время' : 'Запланировать'}</button></div>
      </form>
    </div>}
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
