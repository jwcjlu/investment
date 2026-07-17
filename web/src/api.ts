const API_BASE = '/api'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function getModules() {
  return fetchJson<unknown>('/modules')
}

export function getDaily() {
  return fetchJson<unknown>('/daily')
}

export function getModule(tag: string) {
  return fetchJson<unknown>(`/module/${encodeURIComponent(tag)}`)
}

export function getLesson(id: string) {
  return fetchJson<unknown>(`/lesson/${encodeURIComponent(id)}`)
}

export function completeLesson(id: string) {
  return fetchJson<unknown>(`/lesson/${encodeURIComponent(id)}/complete`, {
    method: 'POST',
  })
}

export function dailyMore() {
  return fetchJson<unknown>('/daily/more', { method: 'POST' })
}

export function getQuiz() {
  return fetchJson<unknown>('/quiz')
}

export function submitQuiz(answers: unknown) {
  return fetchJson<unknown>('/quiz', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answers),
  })
}
