import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import type { DailyResponse, ModulesResponse } from '../api'
import Layout, { ErrorBlock, LoadingBlock } from './Layout'

export default function HomePage() {
  const [modulesData, setModulesData] = useState<ModulesResponse | null>(null)
  const [daily, setDaily] = useState<DailyResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addingMore, setAddingMore] = useState(false)
  const [noMoreHint, setNoMoreHint] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([api.getModules(), api.getDaily()])
      .then(([modules, dailyState]) => {
        if (cancelled) return
        setModulesData(modules)
        setDaily(dailyState)
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
  }, [])

  async function handleMore() {
    setAddingMore(true)
    try {
      const result = await api.dailyMore()
      setDaily(result)
      setNoMoreHint(result.added === 0)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setAddingMore(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <LoadingBlock />
      </Layout>
    )
  }

  if (error || !modulesData) {
    return (
      <Layout>
        <ErrorBlock message={error ?? '未知错误'} />
      </Layout>
    )
  }

  if (modulesData.modules.length === 0) {
    return (
      <Layout>
        <section className="empty-state">
          <h1>还没有可学习的内容</h1>
          <p>
            请先用 <code>read_book.py</code> 精读至少一本书，生成本地缓存后再回来：
          </p>
          <pre>
            <code>python read_book.py 你的书.epub --author 作者名</code>
          </pre>
          <p>精读完成后刷新本页即可看到主题模块。</p>
        </section>
      </Layout>
    )
  }

  const allDailyDone =
    !!daily && daily.lessons.length > 0 && daily.lessons.every((l) => l.completed)

  return (
    <Layout>
      {modulesData.continue_lesson && (
        <section className="continue-banner">
          <Link
            to={`/lesson/${modulesData.continue_lesson.encoded_id}?tag=${modulesData.continue_lesson.encoded_tag}`}
          >
            继续上次学习：{modulesData.continue_lesson.opinion} →
          </Link>
        </section>
      )}

      <section className="daily-section">
        <div className="section-heading">
          <h1>今日清单</h1>
          {daily?.date && <span className="hint">{daily.date}</span>}
        </div>

        {!daily?.tag ? (
          <p className="hint">今日暂无待学的原则类内容，去下面挑一个主题模块看看吧。</p>
        ) : (
          <>
            <p className="hint">
              已学 {modulesData.completed_count} 则观点 · 本组聚焦「{daily.tag}」
            </p>
            {daily.lessons.length === 0 ? (
              <p className="hint">今日清单已清空，试试「再学 5 则」补充一批。</p>
            ) : (
              <ol className="lesson-list">
                {daily.lessons.map((lesson) => (
                  <li
                    key={lesson.lesson_id}
                    className={`lesson-item ${lesson.completed ? 'is-completed' : ''}`}
                  >
                    <Link to={`/lesson/${lesson.encoded_id}?tag=${daily.encoded_tag}`}>
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

            <div className="daily-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={handleMore}
                disabled={addingMore}
              >
                {addingMore ? '加载中…' : '再学 5 则'}
              </button>
              {noMoreHint && <span className="hint">今天该主题暂时没有更多内容了。</span>}
              {allDailyDone && (
                <Link className="btn-primary" to="/quiz?daily=1">
                  去做今日小测
                </Link>
              )}
            </div>
          </>
        )}
      </section>

      <h2>主题模块</h2>
      <p className="hint">课表按「原则 → 可直接执行 → 需自己判断」排列，选择一个主题开始。</p>
      <div className="module-grid">
        {modulesData.modules.map((m) => (
          <Link className="module-card" key={m.tag} to={`/module/${m.encoded_tag}`}>
            <h3>{m.tag}</h3>
            <p className="module-meta">
              {m.count} 则观点 · 已学 {m.done_count}
            </p>
            {m.difficulty && <span className="difficulty-badge">{m.difficulty}</span>}
          </Link>
        ))}
      </div>
    </Layout>
  )
}
