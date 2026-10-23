const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "")

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export type User = {
  id: string
  email: string
  timezone: string
  created_at: string
}

export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled"
export type TaskPriority = "low" | "medium" | "high" | "urgent"

export type ApiTask = {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  category: string
  due_at: string | null
  estimated_minutes: number | null
  created_at: string
  updated_at: string
}

export type TimerState = {
  id: string
  task_id: string | null
  category: string
  started_at: string
  status: "running" | "paused" | "stopped"
  elapsed_seconds: number
  finished_at: string | null
}

export type TimeEntry = {
  id: string
  task_id: string | null
  category: string
  notes: string | null
  started_at: string
  ended_at: string
  duration_seconds: number
  source: string
  created_at: string
}

export type FinanceTransaction = {
  id: string
  kind: 'income' | 'expense'
  amount: string
  currency_code: string
  category: string
  description: string | null
  occurred_at: string
  created_at: string
}
export type FinanceSummary = {
  currency_code: string
  income: string
  expenses: string
  balance: string
  transaction_count: number
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      credentials: "include",
    })
  } catch {
    throw new ApiError("Не удалось связаться с сервером", 0)
  }

  if (!response.ok) {
    let message = `Ошибка запроса (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") {
        message = payload.detail
      } else if (Array.isArray(payload.detail)) {
        const first = payload.detail[0] as { msg?: unknown } | undefined
        if (typeof first?.msg === "string") message = first.msg
      }
    } catch {
      // Keep the status-based fallback for non-JSON error responses.
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  me: () => request<User>("/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, invitationToken: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, invitation_token: invitationToken }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  tasks: () => request<ApiTask[]>("/tasks?limit=200"),
  createTask: (payload: { title: string; category: string; priority: TaskPriority; estimated_minutes?: number }) =>
    request<ApiTask>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (id: string, payload: Partial<Pick<ApiTask, "title" | "description" | "status" | "priority" | "category" | "due_at" | "estimated_minutes">>) =>
    request<ApiTask>(`/tasks/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  currentTimer: () => request<TimerState | null>("/timer/current"),
  startTimer: (category: string, taskId?: string) =>
    request<TimerState>("/timer/start", {
      method: "POST",
      body: JSON.stringify({ category, ...(taskId ? { task_id: taskId } : {}) }),
    }),
  pauseTimer: () => request<TimerState>("/timer/pause", { method: "POST" }),
  resumeTimer: () => request<TimerState>("/timer/resume", { method: "POST" }),
  stopTimer: () => request<TimerState>("/timer/stop", { method: "POST" }),
  timeEntries: () => request<TimeEntry[]>("/time-entries?limit=200"),
  financeTransactions: () => request<FinanceTransaction[]>("/finance/transactions?limit=200"),
  financeSummary: () => request<FinanceSummary[]>("/finance/summary"),
  createFinanceTransaction: (payload: { kind: 'income' | 'expense'; amount: string; currency_code: string; category: string; description?: string; occurred_at: string }) => request<FinanceTransaction>("/finance/transactions", { method: "POST", body: JSON.stringify(payload) }),
  deleteFinanceTransaction: (id: string) => request<void>(`/finance/transactions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  createTimeEntry: (payload: { task_id?: string; category: string; notes?: string; started_at: string; ended_at: string; source?: "manual" | "calendar_adjustment" }) =>
    request<TimeEntry>("/time-entries", { method: "POST", body: JSON.stringify(payload) }),
  updateTimeEntry: (id: string, payload: Partial<Pick<TimeEntry, "task_id" | "category" | "notes" | "started_at" | "ended_at" | "duration_seconds">>) =>
    request<TimeEntry>(`/time-entries/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
}
