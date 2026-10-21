import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Bell, BookOpen, CalendarDays, Check, ChevronDown, CircleHelp, Clock3, Command, Compass, GraduationCap, LayoutDashboard, ListTodo, Plus, Search, Settings2, Sparkles, Timer, UsersRound, Wallet, Zap } from 'lucide-react'

type Task = { id: number; title: string; area: string; time: string; done: boolean; color: string }
const seedTasks: Task[] = [
  { id: 1, title: 'Повторить вопросы к защите веб-лабы', area: 'ITMO · Веб-разработка', time: '45 мин', done: false, color: 'violet' },
  { id: 2, title: 'Разобрать градиентный спуск', area: 'ML · Обучение моделей', time: '60 мин', done: false, color: 'blue' },
  { id: 3, title: 'Подготовить задачи по физике', area: 'Репетиторство', time: '30 мин', done: true, color: 'amber' },
]
const groups = [
  { title: 'РАБОЧЕЕ ПРОСТРАНСТВО', items: [{ label: 'Обзор дня', icon: LayoutDashboard }, { label: 'Планировщик', icon: CalendarDays }, { label: 'Задачи', icon: ListTodo }, { label: 'Фокус и время', icon: Timer }] },
  { title: 'НАПРАВЛЕНИЯ', items: [{ label: 'Учёба', icon: GraduationCap }, { label: 'ML и проекты', icon: Compass }, { label: 'Репетиторство', icon: UsersRound }, { label: 'Финансы', icon: Wallet }] },
]

export default function App() {
  const [tasks, setTasks] = useState(seedTasks)
  const [activePage, setActivePage] = useState('Обзор дня')
  const [query, setQuery] = useState('')
  const [draft, setDraft] = useState('')
  const [composer, setComposer] = useState(false)
  const [running, setRunning] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const done = tasks.filter((task) => task.done).length
  const visible = useMemo(() => tasks.filter((task) => (task.title + task.area).toLowerCase().includes(query.toLowerCase())), [tasks, query])
  const dateLabel = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  const timeLabel = [Math.floor(seconds / 3600), Math.floor(seconds % 3600 / 60), seconds % 60].map((part) => String(part).padStart(2, '0')).join(':')

  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  function addTask() {
    const title = draft.trim()
    if (!title) return
    setTasks((current) => [...current, { id: Date.now(), title, area: 'Личное', time: 'Без оценки', done: false, color: 'violet' }])
    setDraft('')
    setComposer(false)
  }

  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="#home"><span className="brand-mark"><Command size={20}/></span><span><strong>personal<span>OS</span></strong><small>YOUR LIFE, IN SYNC</small></span></a>
      <button className="workspace"><span className="workspace-mark">A</span><span><b>Моё пространство</b><small>Personal workspace</small></span><ChevronDown size={15}/></button>
      <nav>{groups.map((group) => <div className="nav-group" key={group.title}><p>{group.title}</p>{group.items.map(({ label, icon: Icon }) => <button key={label} className={activePage === label ? 'nav-link active' : 'nav-link'} onClick={() => setActivePage(label)}><Icon size={17}/><span>{label}</span>{label === 'Задачи' && <em>{tasks.length - done}</em>}</button>)}</div>)}</nav>
      <div className="side-bottom"><div className="sync"><i/> <span><b>Локальный режим</b><small>Интеграции не подключены</small></span></div><button className="nav-link"><Settings2 size={17}/><span>Настройки</span></button><div className="profile"><div>AS</div><span><b>Мой профиль</b><small>Личный аккаунт</small></span><ChevronDown size={14}/></div></div>
    </aside>
    <main id="home" className="main">
      <header className="topbar"><div className="crumb"><span>Рабочее пространство</span><ArrowRight size={13}/><b>{activePage}</b></div><div className="top-actions"><label className="search"><Search size={15}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по системе..."/><kbd>⌘ K</kbd></label><button className="icon-button" aria-label="Уведомления"><Bell size={18}/><i/></button><div className="avatar">AS</div></div></header>
      <div className="content">
        <section className="welcome"><div><p className="date">{dateLabel}</p><h1>С возвращением, Андрей <span>✳</span></h1><p className="subtitle">Планы становятся результатами. Давай соберём этот день.</p></div><button className="primary" onClick={() => setComposer(true)}><Plus size={17}/> Новая задача</button></section>
        <section className="hero-grid">
          <article className="focus-card"><div className="orb orb-a"/><div className="orb orb-b"/><div className="card-top"><span className="pill"><Sparkles size={13}/> ФОКУС ДНЯ</span><span className="draft-label">План · черновик</span></div><div className="focus-copy"><p>ТВОЯ ГЛАВНАЯ ЦЕЛЬ</p><h2>Сделать важное.<br/>Не просто заняться делами.</h2><span>Выбери одну задачу, которая сдвинет тебя вперёд — в учёбе, ML или проектах.</span></div><div className="focus-bottom"><div><small>Выполнение задач</small><div className="progress"><span style={{width: `${tasks.length ? done / tasks.length * 100 : 0}%`}}/></div></div><b>{done}/{tasks.length}</b><button className="round-arrow" aria-label="К задачам" onClick={() => setActivePage('Задачи')}><ArrowRight size={16}/></button></div></article>
          <article className="timer-card"><div className="timer-top"><span className="timer-icon"><Timer size={17}/></span><span>Фокус-сессия</span><button className="quiet" aria-label="Помощь о таймере"><CircleHelp size={16}/></button></div><p className="timer-label">ТЕКУЩАЯ СЕССИЯ</p><div className="timer-value">{timeLabel}</div><div className="timer-state"><i className={running ? 'live' : ''}/>{running ? 'Таймер запущен' : 'Готов к фокусировке'}</div><div className="timer-bottom"><button className={running ? 'secondary' : 'primary'} onClick={() => setRunning((value) => !value)}>{running ? 'Пауза' : <><Zap size={15}/> Начать фокус</>}</button><span>Без привязки к задаче</span></div></article>
        </section>
        <section className="stats-grid"><article className="stat"><div className="stat-top"><span>Задачи на сегодня</span><i className="violet"><ListTodo size={16}/></i></div><div className="stat-number">{tasks.length - done}<small> / {tasks.length}</small></div><div className="stat-foot"><b>{done} завершено</b><span>из плана дня</span></div></article><article className="stat"><div className="stat-top"><span>Время в фокусе</span><i className="blue"><Clock3 size={16}/></i></div><div className="stat-number">{Math.floor(seconds / 3600)}<small> ч </small>{Math.floor(seconds % 3600 / 60)}<small> мин</small></div><div className="stat-foot"><span>Только измеренный факт</span><span>↗</span></div></article><article className="stat"><div className="stat-top"><span>Главные направления</span><i className="amber"><BookOpen size={16}/></i></div><div className="tags"><span>ITMO</span><span>ML / DS</span><span>Репетиторство</span></div><div className="stat-foot"><span>Баланс по результатам</span><span>4 области</span></div></article></section>
        <section className="lower-grid"><article className="panel"><div className="panel-title"><div><h3>Приоритеты дня</h3><p>Небольшой список, который двигает вперёд</p></div><button className="link-button" onClick={() => setActivePage('Задачи')}>Все задачи <ArrowRight size={14}/></button></div>
          {composer && <form className="composer" onSubmit={(event) => {event.preventDefault(); addTask()}}><input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Что нужно сделать?" aria-label="Новая задача"/><button className="primary" type="submit"><Plus size={15}/> Добавить</button><button type="button" className="quiet" onClick={() => setComposer(false)}>Отмена</button></form>}
          <div className="task-list">{visible.map((task) => <div className={'task-row ' + (task.done ? 'is-done' : '')} key={task.id}><button className={'check ' + (task.done ? 'checked' : '')} aria-label={task.done ? 'Отметить невыполненной' : 'Отметить выполненной'} onClick={() => setTasks((current) => current.map((item) => item.id === task.id ? {...item, done: !item.done} : item))}>{task.done && <Check size={13}/>}</button><div className={'marker ' + task.color}/><div className="task-copy"><b>{task.title}</b><span>{task.area}</span></div><span className="duration">{task.time}</span></div>)}{!visible.length && <p className="empty">Задач по запросу не найдено.</p>}</div><button className="add-link" onClick={() => setComposer(true)}><Plus size={15}/> Добавить задачу в план</button>
        </article><article className="panel"><div className="panel-title"><div><h3>Ритм дня</h3><p>Предварительная структура времени</p></div><button className="quiet" aria-label="Настройки расписания"><Settings2 size={17}/></button></div><div className="schedule"><div className="schedule-row"><time>09:30</time><i className="s-violet"/><div><b>Глубокая работа</b><small>ML · теория и практика</small></div><span>60 мин</span></div><div className="schedule-row"><time>11:00</time><i className="s-blue"/><div><b>Лабораторная работа</b><small>ITMO · срок близко</small></div><span>90 мин</span></div><div className="schedule-row"><time>14:00</time><i className="s-amber"/><div><b>Занятие с учеником</b><small>Репетиторство · пример</small></div><span>60 мин</span></div><div className="schedule-note"><CalendarDays size={15}/><span>Демонстрационный план. События появятся после подключения календаря.</span></div></div></article></section>
        <footer className="footer"><span>PERSONAL OS <b>·</b> FOUNDATION BUILD</span><span><i/> Данные задач пока живут в состоянии интерфейса, не в базе данных</span></footer>
      </div>
    </main>
  </div>
}
