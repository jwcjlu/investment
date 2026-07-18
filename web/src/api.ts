const API_BASE = '/api'

export interface ModuleCard {
  tag: string
  encoded_tag: string
  count: number
  difficulty: string
  done_count: number
}

export interface LessonBrief {
  lesson_id: string
  encoded_id: string
  opinion: string
  book_title: string
  chapter: string
  actionability: string
  completed: boolean
}

export interface ContinueLesson {
  opinion: string
  encoded_id: string
  encoded_tag: string
}

export interface ModulesResponse {
  modules: ModuleCard[]
  completed_count: number
  continue_lesson: ContinueLesson | null
}

export interface ModuleIntro {
  tag: string
  goals: string
  cross_book: string
  study_order_note: string
  source: 'ai' | 'placeholder'
}

export interface ModuleDetail {
  tag: string
  encoded_tag: string
  intro: ModuleIntro
  lessons: LessonBrief[]
}

export interface ChapterNote {
  chapter_title: string
  core_points: string[]
  arguments: string[]
  actionables: string[]
  quotes: string[]
}

export interface LessonDetail {
  lesson_id: string
  encoded_id: string
  tag: string
  encoded_tag: string
  book_title: string
  chapter: string
  opinion: string
  argument_summary: string
  actionability: string
  quote: string
  completed: boolean
  chapter_note: ChapterNote | null
  next_lesson_id: string | null
  next_encoded_id: string | null
}

export interface DailyResponse {
  date: string | null
  tag: string | null
  encoded_tag: string | null
  extra_batches: number
  lesson_ids: string[]
  lessons: LessonBrief[]
}

export interface DailyMoreResponse extends DailyResponse {
  added: number
}

export interface QuizQuestion {
  id: string
  stem: string
  options: string[]
  answer_index: number
  explanation: string
}

export interface QuizResponse {
  tag: string
  source: 'ai' | 'placeholder'
  questions: QuizQuestion[]
  encoded_tag: string
}

export interface QuizSubmitDetail {
  id: string
  correct: boolean
  explanation: string
}

export interface QuizSubmitResponse {
  score: number
  details: QuizSubmitDetail[]
}

export interface ProgressResponse {
  completed: string[]
  last_lesson_id: string | null
  updated_at: string | null
}

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    let detail = ''
    try {
      const data = await res.json()
      detail = typeof data?.detail === 'string' ? data.detail : ''
    } catch {
      // 响应体不是 JSON，忽略
    }
    throw new ApiError(detail || `请求失败（${res.status}）`, res.status)
  }
  return res.json() as Promise<T>
}

export function getModules() {
  return fetchJson<ModulesResponse>('/modules')
}

export function getModule(tag: string) {
  return fetchJson<ModuleDetail>(`/modules/${encodeURIComponent(tag)}`)
}

export function getLesson(encodedId: string, tag: string, expand = false) {
  const params = new URLSearchParams({ tag })
  if (expand) params.set('expand', '1')
  return fetchJson<LessonDetail>(`/lessons/${encodedId}?${params.toString()}`)
}

export function completeLesson(lessonId: string) {
  return fetchJson<{ ok: boolean }>('/progress', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson_id: lessonId }),
  })
}

export function getProgress() {
  return fetchJson<ProgressResponse>('/progress')
}

export function getDaily(tag?: string) {
  const params = new URLSearchParams()
  if (tag) params.set('tag', tag)
  const qs = params.toString()
  return fetchJson<DailyResponse>(`/daily${qs ? `?${qs}` : ''}`)
}

export function dailyMore() {
  return fetchJson<DailyMoreResponse>('/daily/more', { method: 'POST' })
}

export function getQuiz(opts: { tag?: string; daily?: boolean; force?: boolean } = {}) {
  const params = new URLSearchParams()
  if (opts.tag) params.set('tag', opts.tag)
  if (opts.daily) params.set('daily', '1')
  if (opts.force) params.set('force', '1')
  return fetchJson<QuizResponse>(`/quiz?${params.toString()}`)
}

export function submitQuiz(tag: string, answers: Record<string, number>) {
  return fetchJson<QuizSubmitResponse>('/quiz/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag, answers }),
  })
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}
