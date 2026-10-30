import { useMemo, useRef, useState } from 'react'
import { BookOpen, ExternalLink, FileDown, FileUp, FolderOpen, Heart, Link2, Plus, Search, Trash2, X } from 'lucide-react'

type LibraryItem = { id: string; title: string; type: string; kind: string; subject: string; student: string; target: string; notes: string; favorite?: boolean; created?: number }
type ExportFile = { app?: string; version?: number; exportedAt?: string; items: LibraryItem[] }
const STORAGE_KEY = 'personal-os-study-library-v1'
const QUICK_LINKS: LibraryItem[] = [
  { id:'quick-polyakov', title:'К. Поляков — материалы по информатике', type:'Полезный сайт', kind:'Сайт', subject:'Информатика', student:'', target:'https://kpolyakov.spb.ru/', notes:'Задания и материалы по информатике', favorite:true },
  { id:'quick-shkolkovo', title:'Школково', type:'Полезный сайт', kind:'Сайт', subject:'Общее', student:'', target:'https://3.shkolkovo.online/catalogs', notes:'Каталоги заданий и подготовка', favorite:false },
  { id:'quick-ege', title:'Решу ЕГЭ', type:'Полезный сайт', kind:'Сайт', subject:'Общее', student:'', target:'https://ege.sdamgia.ru/', notes:'Банк заданий ЕГЭ', favorite:false },
  { id:'quick-oge', title:'Решу ОГЭ', type:'Полезный сайт', kind:'Сайт', subject:'Общее', student:'', target:'https://oge.sdamgia.ru/', notes:'Банк заданий ОГЭ', favorite:false },
]
function readItems(): LibraryItem[] {
  try { const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as unknown; return Array.isArray(parsed) ? parsed as LibraryItem[] : [] } catch { return [] }
}
function safeTarget(target: string) {
  return /^(https?:\/\/|file:\/\/)/i.test(target) || /^[a-zA-Z]:\\/.test(target) || /^\\\\/.test(target)
}
export default function StudyLibraryPanel() {
  const [items, setItems] = useState<LibraryItem[]>(readItems)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('Все')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [editing, setEditing] = useState<LibraryItem | null>(null)
  const [draft, setDraft] = useState<LibraryItem>({ id:'', title:'', type:'Материал', kind:'Сайт', subject:'Общее', student:'', target:'', notes:'', favorite:false, created:Date.now() })
  const [notice, setNotice] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const allItems = useMemo(() => [...items, ...QUICK_LINKS.filter((item) => !items.some((saved) => saved.id === item.id))], [items])
  const types = useMemo(() => ['Все', ...Array.from(new Set(allItems.map((item) => item.type))).sort()], [allItems])
  const visible = useMemo(() => allItems.filter((item) => {
    const text = `${item.title} ${item.type} ${item.kind} ${item.subject} ${item.student} ${item.notes}`.toLowerCase()
    return (!query || text.includes(query.toLowerCase())) && (filter === 'Все' || item.type === filter) && (!favoritesOnly || item.favorite)
  }).sort((a,b) => Number(Boolean(b.favorite))-Number(Boolean(a.favorite)) || (b.created ?? 0)-(a.created ?? 0)), [allItems, filter, favoritesOnly, query])
  function persist(next: LibraryItem[]) { setItems(next); try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { setNotice('Не удалось сохранить данные браузера. Экспортируй резервную копию.') } }
  function openNew() { setEditing(null); setDraft({ id:crypto.randomUUID(), title:'', type:'Материал', kind:'Сайт', subject:'Общее', student:'', target:'', notes:'', favorite:false, created:Date.now() }) }
  function saveItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.title.trim() || !safeTarget(draft.target.trim())) { setNotice('Укажи название и корректную ссылку или локальный путь.'); return }
    const next = editing ? items.map((item) => item.id === draft.id ? { ...draft, title:draft.title.trim(), target:draft.target.trim() } : item) : [{ ...draft, title:draft.title.trim(), target:draft.target.trim() }, ...items]
    persist(next); setEditing(null); setNotice('Материал сохранён.')
  }
  function editItem(item: LibraryItem) { if (item.id.startsWith('quick-')) return; setEditing(item); setDraft(item) }
  function removeItem(item: LibraryItem) { if (item.id.startsWith('quick-')) return; if (window.confirm(`Удалить «${item.title}»?`)) persist(items.filter((saved) => saved.id !== item.id)) }
  function toggleFavorite(item: LibraryItem) { if (item.id.startsWith('quick-')) return; persist(items.map((saved) => saved.id === item.id ? { ...saved, favorite: !saved.favorite } : saved)) }
  function openTarget(item: LibraryItem) {
    if (/^[a-zA-Z]:\\/.test(item.target) || /^\\\\/.test(item.target)) {
      const vscodePath = item.target.replace(/\\/g, '/')
      window.location.href = `vscode://file/${encodeURI(vscodePath)}`
    } else if (item.target.startsWith('file://')) {
      window.open(item.target, '_blank', 'noopener,noreferrer')
      setNotice('Локальные file:// ссылки могут блокироваться браузером. Если файл не открылся, проверь путь на этом компьютере.')
    } else window.open(item.target, '_blank', 'noopener,noreferrer')
  }
  async function exportJson() {
    const blob = new Blob([JSON.stringify({ app:'Учебная библиотека', version:1, exportedAt:new Date().toISOString(), items }, null, 2)], { type:'application/json' })
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download='personal-os-library-backup.json'; a.click(); URL.revokeObjectURL(url)
  }
  async function importJson(file?: File) {
    if (!file) return
    try {
      const parsed = JSON.parse(await file.text()) as ExportFile
      if (!parsed || !Array.isArray(parsed.items)) throw new Error('В JSON нет массива items.')
      const normalized = parsed.items.filter((item) => item && typeof item.title === 'string' && typeof item.target === 'string' && safeTarget(item.target)).map((item) => ({ ...item, id: item.id || crypto.randomUUID(), type: item.type || 'Материал', kind: item.kind || 'Сайт', subject: item.subject || 'Общее', student: item.student || '', notes: item.notes || '', favorite: Boolean(item.favorite), created: Number(item.created) || Date.now() }))
      const byId = new Map(items.map((item) => [item.id, item])); normalized.forEach((item) => byId.set(item.id, item))
      persist(Array.from(byId.values())); setNotice(`Импортировано записей: ${normalized.length}. Существующие записи с теми же ID обновлены.`)
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Не удалось прочитать JSON.') }
    finally { if (fileRef.current) fileRef.current.value = '' }
  }
  return <section className="area-page">
    <div className="welcome"><div><p className="date">МАТЕРИАЛЫ И ССЫЛКИ</p><h1>Библиотека</h1><p className="subtitle">Конспекты учеников, учебные материалы, таблицы, проекты и полезные сайты — в одном месте.</p></div><button className="primary" onClick={openNew}><Plus size={16}/> Добавить</button></div>
    {notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Закрыть">×</button></div>}
    <article className="panel library-toolbar"><label className="library-search"><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по названию, ученику, предмету…"/></label><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Тип материала">{types.map((type) => <option key={type}>{type}</option>)}</select><button className={favoritesOnly ? 'theme-option selected' : 'theme-option'} onClick={() => setFavoritesOnly((value) => !value)}><Heart size={14}/> Избранное</button><button className="quiet" onClick={() => fileRef.current?.click()}><FileUp size={15}/> Импорт JSON</button><button className="quiet" onClick={() => void exportJson()}><FileDown size={15}/> Экспорт</button><input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={(event) => void importJson(event.target.files?.[0])}/></article>
    {editing !== null || draft.id ? <article className="panel library-editor"><div className="panel-title"><div><h3>{editing ? 'Редактировать материал' : 'Новый материал'}</h3><p>Локальные пути и ссылки сохраняются в этом браузере.</p></div><button className="quiet" onClick={() => { setEditing(null); setDraft({ id:'', title:'', type:'Материал', kind:'Сайт', subject:'Общее', student:'', target:'', notes:'', favorite:false }) }}><X size={16}/></button></div><form className="library-form" onSubmit={saveItem}><label>Название<input value={draft.title} onChange={(e) => setDraft({ ...draft, title:e.target.value })} required maxLength={200}/></label><label>Тип<input value={draft.type} onChange={(e) => setDraft({ ...draft, type:e.target.value })} required maxLength={80}/></label><label>Вид<select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind:e.target.value })}><option>Сайт</option><option>Google Drive</option><option>Google Sheets</option><option>Локальный файл</option><option>Проект VS Code</option></select></label><label>Предмет<input value={draft.subject} onChange={(e) => setDraft({ ...draft, subject:e.target.value })}/></label><label>Ученик<input value={draft.student} onChange={(e) => setDraft({ ...draft, student:e.target.value })}/></label><label className="wide">Ссылка или локальный путь<input value={draft.target} onChange={(e) => setDraft({ ...draft, target:e.target.value })} placeholder="https://… или C:\\Users\\… или file:///…" required/></label><label className="wide">Описание<textarea value={draft.notes} onChange={(e) => setDraft({ ...draft, notes:e.target.value })} rows={2}/></label><label className="library-favorite"><input type="checkbox" checked={Boolean(draft.favorite)} onChange={(e) => setDraft({ ...draft, favorite:e.target.checked })}/> В избранное</label><div className="library-form-actions"><button className="primary" type="submit">Сохранить</button><button className="quiet" type="button" onClick={() => { setEditing(null); setDraft({ ...draft, id:'' }) }}>Отмена</button></div></form></article> : null}
    <div className="library-grid">{visible.map((item) => <article className="panel library-card" key={item.id}><div className="library-card-top"><span className="module-icon">{item.kind.includes('Проект') ? <FolderOpen size={18}/> : <BookOpen size={18}/>}</span><button className={item.favorite ? 'favorite-button active' : 'favorite-button'} aria-label="Избранное" onClick={() => toggleFavorite(item)}><Heart size={16} fill={item.favorite ? 'currentColor' : 'none'}/></button></div><div className="library-card-copy"><span className="library-meta">{item.type} · {item.subject}{item.student ? ` · ${item.student}` : ''}</span><h3>{item.title}</h3><p>{item.notes || item.kind}</p></div><div className="library-card-actions"><button className="primary" onClick={() => openTarget(item)}><ExternalLink size={14}/> Открыть</button>{!item.id.startsWith('quick-') && <><button className="quiet" onClick={() => editItem(item)}>Изменить</button><button className="quiet" onClick={() => removeItem(item)} aria-label="Удалить"><Trash2 size={14}/></button></>}</div></article>)}</div>
    {!visible.length && <div className="panel empty"><Link2 size={20}/><b>Ничего не найдено</b><span>Добавь ссылку или измени фильтр. Можно импортировать резервную копию старой библиотеки.</span></div>}
  </section>
}
