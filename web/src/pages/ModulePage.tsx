import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import * as api from '../api'
import type { ModuleDetail } from '../api'
import Layout, { ErrorBlock, LoadingBlock } from './Layout'

export default function ModulePage() {
  const splat = useParams()['*'] ?? ''
  const tag = decodeURIComponent(splat)

  const [data, setData] = useState<ModuleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!tag) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getModule(tag)
      .then((detail) => {
        if (!cancelled) setData(detail)
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
  }, [tag])

  const breadcrumb = (
    <>
      <Link to="/">首页</Link> / {tag}
    </>
  )

  if (loading) {
    return (
      <Layout breadcrumb={breadcrumb}>
        <LoadingBlock />
      </Layout>
    )
  }

  if (error || !data) {
    return (
      <Layout breadcrumb={breadcrumb}>
        <ErrorBlock message={error ?? '模块不存在'} />
      </Layout>
    )
  }

  return (
    <Layout breadcrumb={breadcrumb}>
      <h1>{data.tag}</h1>

      <section className="module-intro">
        <h2>模块目标</h2>
        <p>{data.intro.goals}</p>
        <h2>跨书对照</h2>
        <p>{data.intro.cross_book}</p>
        <h2>学习顺序建议</h2>
        <p>{data.intro.study_order_note}</p>
        {data.intro.source === 'placeholder' && (
          <p className="hint">（占位导读，未调用 AI 生成）</p>
        )}
      </section>

      <div className="module-actions">
        <Link className="btn-primary" to={`/quiz?tag=${data.encoded_tag}`}>
          开始练习
        </Link>
      </div>

      <h2>课表</h2>
      {data.lessons.length === 0 ? (
        <p className="hint">该模块暂无观点。</p>
      ) : (
        <ol className="lesson-list">
          {data.lessons.map((lesson) => (
            <li
              key={lesson.lesson_id}
              className={`lesson-item ${lesson.completed ? 'is-completed' : ''}`}
            >
              <Link to={`/lesson/${lesson.encoded_id}?tag=${data.encoded_tag}`}>
                {lesson.completed ? '✅ ' : ''}
                {lesson.opinion}
              </Link>
              <span className="lesson-meta">
                《{lesson.book_title}》{lesson.chapter} ·{' '}
                <span className="actionability-badge">{lesson.actionability}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </Layout>
  )
}
