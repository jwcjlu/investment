import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import type { LessonDetail, NoteAtom, SourceRef } from '../api'
import LogicPanel from '../components/LogicPanel'
import SourceDrawer from '../components/SourceDrawer'
import Layout, { ErrorBlock, LoadingBlock } from './Layout'

function atomText(item: NoteAtom | string): string {
  return typeof item === 'string' ? item : item.text
}

function atomSources(item: NoteAtom | string): SourceRef[] {
  return typeof item === 'string' ? [] : item.sources || []
}

function SourceButton({
  sources,
  onOpen,
}: {
  sources: SourceRef[]
  onOpen: (ref: SourceRef) => void
}) {
  if (!sources?.length) return null
  return (
    <button type="button" className="btn-link source-btn" onClick={() => onOpen(sources[0])}>
      原文
    </button>
  )
}

export default function LessonPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const encodedTag = searchParams.get('tag') ?? ''

  const [lesson, setLesson] = useState<LessonDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [noteLoading, setNoteLoading] = useState(false)
  const [marking, setMarking] = useState(false)
  const [activeSource, setActiveSource] = useState<SourceRef | null>(null)

  useEffect(() => {
    if (!id || !encodedTag) {
      setError('缺少课程或模块参数')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getLesson(id, encodedTag)
      .then((detail) => {
        if (!cancelled) setLesson(detail)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, encodedTag])

  async function handleExpandNotes(open: boolean) {
    if (!open || !id || !lesson || lesson.chapter_note || noteLoading) return
    setNoteLoading(true)
    try {
      const detail = await api.getLesson(id, encodedTag, true)
      setLesson(detail)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setNoteLoading(false)
    }
  }

  async function handleComplete() {
    if (!lesson) return
    setMarking(true)
    try {
      await api.completeLesson(lesson.lesson_id)
      setLesson({ ...lesson, completed: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setMarking(false)
    }
  }

  const breadcrumb = (
    <>
      <Link to="/">首页</Link>
      {lesson && (
        <>
          {' / '}
          <Link to={`/module/${lesson.encoded_tag}`}>{lesson.tag}</Link>
        </>
      )}
    </>
  )

  if (loading) {
    return (
      <Layout breadcrumb={breadcrumb}>
        <LoadingBlock />
      </Layout>
    )
  }

  if (error || !lesson) {
    return (
      <Layout breadcrumb={breadcrumb}>
        <ErrorBlock message={error ?? '课程不存在'} />
      </Layout>
    )
  }

  return (
    <Layout breadcrumb={breadcrumb}>
      <article className={`lesson ${activeSource ? 'with-drawer' : ''}`}>
        <h1>
          {lesson.opinion}{' '}
          <SourceButton sources={lesson.sources || []} onOpen={setActiveSource} />
        </h1>
        <p className="lesson-meta">
          《{lesson.book_title}》{lesson.chapter} ·{' '}
          <span className="actionability-badge">{lesson.actionability}</span>
        </p>

        {id && (
          <LogicPanel
            encodedId={id}
            encodedTag={encodedTag}
            onOpenSource={setActiveSource}
          />
        )}

        <section>
          <h2>论据摘要</h2>
          <p>{lesson.argument_summary}</p>
        </section>

        <details
          className="chapter-expand"
          onToggle={(e) => handleExpandNotes((e.target as HTMLDetailsElement).open)}
        >
          <summary>原文金句 &amp; 章节笔记</summary>
          <blockquote>
            {lesson.quote}{' '}
            <SourceButton sources={lesson.sources || []} onOpen={setActiveSource} />
          </blockquote>

          {noteLoading && <p className="hint">加载章节笔记中…</p>}

          {lesson.chapter_note ? (
            <div className="chapter-note">
              <h3>章节笔记：{lesson.chapter_note.chapter_title}</h3>
              <h4>核心观点（原始要点）</h4>
              <ul>
                {lesson.chapter_note.core_points.map((p, i) => (
                  <li key={i}>
                    {atomText(p)}{' '}
                    <SourceButton sources={atomSources(p)} onOpen={setActiveSource} />
                  </li>
                ))}
              </ul>
              <h4>论据</h4>
              <ul>
                {lesson.chapter_note.arguments.map((a, i) => (
                  <li key={i}>
                    {atomText(a)}{' '}
                    <SourceButton sources={atomSources(a)} onOpen={setActiveSource} />
                  </li>
                ))}
              </ul>
              <h4>可执行建议</h4>
              <ul>
                {lesson.chapter_note.actionables.map((a, i) => (
                  <li key={i}>
                    {atomText(a)}{' '}
                    <SourceButton sources={atomSources(a)} onOpen={setActiveSource} />
                  </li>
                ))}
              </ul>
              <h4>原文金句</h4>
              <ul>
                {lesson.chapter_note.quotes.map((q, i) => (
                  <li key={i}>
                    {atomText(q)}{' '}
                    <SourceButton sources={atomSources(q)} onOpen={setActiveSource} />
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            !noteLoading && <p className="hint">展开查看该章节的完整笔记。</p>
          )}
        </details>

        <section className="lesson-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleComplete}
            disabled={marking}
          >
            {lesson.completed ? '✅ 已学完（再次标记）' : marking ? '标记中…' : '标记为已学'}
          </button>
          {lesson.next_encoded_id ? (
            <Link
              className="next-lesson"
              to={`/lesson/${lesson.next_encoded_id}?tag=${lesson.encoded_tag}`}
            >
              下一课 →
            </Link>
          ) : (
            <Link className="next-lesson" to={`/module/${lesson.encoded_tag}`}>
              本模块已学完，返回模块 →
            </Link>
          )}
        </section>
      </article>

      <SourceDrawer source={activeSource} onClose={() => setActiveSource(null)} />
    </Layout>
  )
}
