import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, BookOpen, CheckCircle2, Clock3, Plus, UsersRound } from 'lucide-react'
import { api, type DailyAnalytics, type Project, type Student, type Subject, type TimeEntry } from './api'

type Props = { page: string }

export default function ModulePanel({ page }: Props) {
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [entries, setEntries] = useState<TimeEntry[]>([])
  const [daily, setDaily] = useState<DailyAnalytics | null>(null)
  const [name, setName] = useState('')
  const [subject, setSubject] = useState('')
  const [semester, setSemester] = useState('2026 осень')
  const [rate, setRate] = useState('30')
  const [currency, setCurrency] = useState('EUR')
  const [projectType, setProjectType] = useState('ml')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      if (page === 'Репетиторство') setStudents(await api.students())
      else if (page === 'Учёба') setSubjects(await api.subjects())
      else if (page === 'ML и проекты') setProjects(await api.projects())
      else if (page === 'Фокус и время') setEntries(await api.timeEntries())
      else if (page === 'Обзор дня') setDaily(await api.dailyAnalytics())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось загрузить данные')
    }
  }, [page])

  useEffect(() => { void load() }, [load])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (page === 'Репетиторство') {
        await api.createStudent({ name: name.trim(), subject: subject.trim(), rate_amount: Number(rate), currency_code: currency.toUpperCase() })
        setName('')
        setSubject('')
        setStudents(await api.students())
      } else if (page === 'Учёба') {
        await api.createSubject({ name: name.trim(), semester: semester.trim() })
        setName('')
        setSubjects(await api.subjects())
      } else if (page === 'ML и проекты') {
        await api.createProject({ name: name.trim(), project_type: projectType })
        setName('')
        setProjects(await api.projects())
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось сохранить')
    } finally {
      setBusy(false)
    }
  }

  const trackedSeconds = entries.reduce((total, entry) => total + entry.duration_seconds, 0)
  const trackedLabel = `${Math.floor(trackedSeconds / 3600)} ч ${Math.floor((trackedSeconds % 3600) / 60)} мин`

  return <section className="module-page">
    <div className="module-heading">
      <div>
        <p className="date">PERSONAL OS · РАЗДЕЛ</p>
        <h1>{page}</h1>
        <p className="subtitle">Данные загружаются из Personal OS API и сохраняются в PostgreSQL.</p>
      </div>
    </div>
    {error && <div className="auth-error" role="alert">{error}</div>}

    {page === 'Репетиторство' && <>
      <div className="module-stats"><article className="stat"><div className="stat-top"><span>Ученики</span><i className="violet"><UsersRound size={16}/></i></div><div className="stat-number">{students.length}</div><div className="stat-foot"><span>Активные и архивные исключены</span></div></article><article className="stat"><div className="stat-top"><span>Учёт занятий</span><i className="blue"><CheckCircle2 size={16}/></i></div><div className="stat-number">CRM</div><div className="stat-foot"><span>Занятия, ДЗ и платежи через API</span></div></article></div>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Добавить ученика</h3><p>Ставка, предмет и валюта оплаты</p></div></div><form className="module-form" onSubmit={submit}><input required value={name} onChange={e => setName(e.target.value)} placeholder="Имя ученика"/><input required value={subject} onChange={e => setSubject(e.target.value)} placeholder="Предмет"/><input required type="number" min="0" step="0.01" value={rate} onChange={e => setRate(e.target.value)} placeholder="Цена занятия"/><select value={currency} onChange={e => setCurrency(e.target.value)}><option>EUR</option><option>RUB</option><option>USD</option></select><button className="primary" type="submit" disabled={busy}><Plus size={15}/> Добавить</button></form></article>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Ученики</h3><p>Ставки хранятся отдельно от фактических платежей</p></div></div>{students.length ? <div className="module-list">{students.map(item => <div className="module-row" key={item.id}><div className="module-avatar">{item.name.slice(0,1).toUpperCase()}</div><div><b>{item.name}</b><small>{item.subject} · {item.status}</small></div><strong>{item.rate_amount} {item.currency_code}</strong></div>)}</div> : <p className="empty">Пока нет учеников. Добавь первого выше.</p>}</article>
    </>}

    {page === 'Учёба' && <>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Добавить дисциплину</h3><p>Внутри дисциплины можно вести лабораторные, дедлайны и темы</p></div></div><form className="module-form" onSubmit={submit}><input required value={name} onChange={e => setName(e.target.value)} placeholder="Например, Алгоритмы и структуры данных"/><input required value={semester} onChange={e => setSemester(e.target.value)} placeholder="Семестр"/><button className="primary" type="submit" disabled={busy}><Plus size={15}/> Добавить</button></form></article>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Дисциплины</h3><p>Учебный прогресс и результаты</p></div></div>{subjects.length ? <div className="module-list">{subjects.map(item => <div className="module-row" key={item.id}><div className="module-avatar"><BookOpen size={17}/></div><div><b>{item.name}</b><small>{item.semester} · {item.status}</small></div><ArrowRight size={16}/></div>)}</div> : <p className="empty">Дисциплины ещё не добавлены.</p>}</article>
    </>}

    {page === 'ML и проекты' && <>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Новый проект</h3><p>ML/DS, разработка, учебный или личный проект</p></div></div><form className="module-form" onSubmit={submit}><input required value={name} onChange={e => setName(e.target.value)} placeholder="Название проекта"/><select value={projectType} onChange={e => setProjectType(e.target.value)}><option value="ml">ML / Data Science</option><option value="software">Разработка ПО</option><option value="study">Учебный</option><option value="personal">Личный</option><option value="other">Другое</option></select><button className="primary" type="submit" disabled={busy}><Plus size={15}/> Создать</button></form></article>
      <article className="panel module-panel"><div className="panel-title"><div><h3>Проекты</h3><p>Стадии, milestones и репозитории связываются с проектом</p></div></div>{projects.length ? <div className="module-list">{projects.map(item => <div className="module-row" key={item.id}><div className="module-avatar"><BookOpen size={17}/></div><div><b>{item.name}</b><small>{item.project_type} · {item.status}</small></div><ArrowRight size={16}/></div>)}</div> : <p className="empty">Проектов пока нет.</p>}</article>
    </>}

    {page === 'Фокус и время' && <article className="panel module-panel"><div className="panel-title"><div><h3>Фактическое время</h3><p>Записи из таймера и ручного ввода</p></div><i className="blue"><Clock3 size={16}/></i></div><div className="stat-number">{trackedLabel}</div>{entries.length ? <div className="module-list">{entries.slice(0, 30).map(entry => <div className="module-row" key={entry.id}><div className="module-avatar"><Clock3 size={16}/></div><div><b>{entry.category}</b><small>{new Date(entry.started_at).toLocaleString('ru-RU')} · {entry.source}</small></div><strong>{Math.round(entry.duration_seconds / 60)} мин</strong></div>)}</div> : <p className="empty">Пока нет сохранённых сессий. Запусти таймер на обзоре дня.</p>}</article>}

    {page === 'Финансы' && <article className="panel module-panel"><div className="panel-title"><div><h3>Финансы</h3><p>Полный учёт личных расходов — следующий этап</p></div></div><p className="subtitle">Сейчас Personal OS отдельно хранит начисления за проведённые занятия и реальные платежи. В этом разделе позже появятся импорт банковских выписок, категории расходов и анализ регулярных трат.</p></article>}

    {page === 'Планировщик' && <article className="panel module-panel"><div className="panel-title"><div><h3>Календарь</h3><p>Сначала подключи Google Calendar, затем синхронизируй события.</p></div></div><button className="primary" onClick={async () => { try { const response = await api.connectGoogleCalendar(); window.location.assign(response.authorization_url) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Не удалось начать подключение') } }}>Подключить Google Calendar <ArrowRight size={15}/></button></article>}

    {page === 'Задачи' && <article className="panel module-panel"><div className="panel-title"><div><h3>Список задач</h3><p>Создавай и закрывай задачи на обзоре дня</p></div></div><p className="subtitle">Список задач сохраняется в базе. Перейди в «Обзор дня», чтобы добавить задачу или изменить статус.</p></article>}
    {page === 'Обзор дня' && daily && <article className="panel module-panel"><div className="panel-title"><div><h3>Итоги дня</h3><p>{daily.day}</p></div></div><div className="module-list"><div className="module-row"><b>Задачи выполнены</b><strong>{daily.completed_tasks}</strong></div><div className="module-row"><b>Учебные результаты</b><strong>{daily.completed_academic_items}</strong></div><div className="module-row"><b>Занятия</b><strong>{daily.completed_lessons}</strong></div></div></article>}
  </section>
}
