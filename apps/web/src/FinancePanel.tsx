import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ArrowDownRight, ArrowUpRight, Plus, RefreshCw, Trash2, Wallet } from 'lucide-react'
import { api, type FinanceSummary, type FinanceTransaction } from './api'

function localDateTime() {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function money(amount: string | number, currency: string) {
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(amount))
}

export default function FinancePanel() {
  const [items, setItems] = useState<FinanceTransaction[]>([])
  const [summaries, setSummaries] = useState<FinanceSummary[]>([])
  const [kind, setKind] = useState<'income' | 'expense'>('expense')
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState('EUR')
  const [category, setCategory] = useState('Ежедневные расходы')
  const [description, setDescription] = useState('')
  const [occurredAt, setOccurredAt] = useState(localDateTime)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const [transactions, totals] = await Promise.all([api.financeTransactions(), api.financeSummary()])
      setItems(transactions)
      setSummaries(totals)
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось загрузить финансы') }
  }, [])
  useEffect(() => { void load() }, [load])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      const parsed = Number(amount)
      if (!Number.isFinite(parsed) || parsed <= 0) throw new Error('Сумма должна быть положительным числом.')
      await api.createFinanceTransaction({ kind, amount: parsed.toFixed(2), currency_code: currency, category: category.trim(), description: description.trim() || undefined, occurred_at: new Date(occurredAt).toISOString() })
      setAmount(''); setDescription('')
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось сохранить операцию') }
    finally { setBusy(false) }
  }

  async function remove(id: string) {
    if (!window.confirm('Удалить эту финансовую операцию?')) return
    try { await api.deleteFinanceTransaction(id); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось удалить операцию') }
  }

  return <section className="module-page finance-page">
    <div className="module-heading"><div><p className="date">PERSONAL OS · ЛИЧНЫЙ БЮДЖЕТ</p><h1>Финансы</h1><p className="subtitle">Записывай фактические доходы и расходы. Баланс считается отдельно для каждой валюты.</p></div><button className="secondary" onClick={() => void load()}><RefreshCw size={15}/> Обновить</button></div>
    {error && <div className="auth-error" role="alert">{error}</div>}
    <div className="module-stats">{summaries.length ? summaries.map(s => <article className="stat" key={s.currency_code}><div className="stat-top"><span>Баланс · {s.currency_code}</span><i className="violet"><Wallet size={16}/></i></div><div className="stat-number">{money(s.balance, s.currency_code)}</div><div className="stat-foot"><span>Доходы {money(s.income, s.currency_code)}</span><span>Расходы {money(s.expenses, s.currency_code)}</span></div></article>) : <article className="stat"><div className="stat-top"><span>Пока нет операций</span><i className="violet"><Wallet size={16}/></i></div><div className="stat-number">—</div><div className="stat-foot"><span>Добавь первую операцию ниже</span></div></article>}</div>
    <article className="panel"><div className="panel-title"><div><h3>Добавить операцию</h3><p>Сохраняются только введённые тобой реальные суммы — никаких демоданных.</p></div></div>
      <form className="finance-form" onSubmit={event => void submit(event)}>
        <label>Тип<select value={kind} onChange={e => setKind(e.target.value as 'income' | 'expense')}><option value="expense">Расход</option><option value="income">Доход</option></select></label>
        <label>Сумма<input type="number" min="0.01" step="0.01" required value={amount} onChange={e => setAmount(e.target.value)} placeholder="0,00"/></label>
        <label>Валюта<select value={currency} onChange={e => setCurrency(e.target.value)}><option>EUR</option><option>USD</option><option>RUB</option><option>GBP</option></select></label>
        <label>Категория<input required maxLength={80} value={category} onChange={e => setCategory(e.target.value)} placeholder="Например, транспорт"/></label>
        <label>Дата и время<input type="datetime-local" required value={occurredAt} onChange={e => setOccurredAt(e.target.value)}/></label>
        <label className="finance-description">Комментарий<input maxLength={1000} value={description} onChange={e => setDescription(e.target.value)} placeholder="Необязательно"/></label>
        <button className="primary" type="submit" disabled={busy}>{busy ? 'Сохраняю…' : <><Plus size={15}/> Добавить операцию</>}</button>
      </form>
    </article>
    <article className="panel"><div className="panel-title"><div><h3>История операций</h3><p>{items.length} последних записей</p></div></div>
      {!items.length ? <div className="empty"><Wallet size={20}/><b>История пока пустая</b><span>Добавь доход или расход — он появится здесь после сохранения в базе.</span></div> : <div className="finance-list">{items.map(item => <div className="finance-row" key={item.id}><span className={'finance-kind ' + item.kind}>{item.kind === 'income' ? <ArrowDownRight size={17}/> : <ArrowUpRight size={17}/>}</span><div className="finance-copy"><b>{item.category}</b><span>{item.description || (item.kind === 'income' ? 'Доход' : 'Расход')} · {new Intl.DateTimeFormat('ru-RU', {day:'numeric',month:'short',year:'numeric'}).format(new Date(item.occurred_at))}</span></div><strong className={item.kind === 'income' ? 'income-amount' : 'expense-amount'}>{item.kind === 'income' ? '+' : '−'}{money(item.amount, item.currency_code)}</strong><button className="quiet" aria-label="Удалить операцию" title="Удалить операцию" onClick={() => void remove(item.id)}><Trash2 size={15}/></button></div>)}</div>}
    </article>
    <article className="panel area-tip"><Wallet size={18}/><div><b>Важно</b><p>Это ручной учёт доходов и расходов. Банковские счета не подключаются, автоматического импорта выписок нет. Не смешивай разные валюты в одной сумме — сводка разделяет их.</p></div></article>
  </section>
}