import { useEffect, useState } from 'react'
import * as api from '../api'
import type { SourceRef, SourceWindow } from '../api'

type Props = {
  source: SourceRef | null
  onClose: () => void
}

export default function SourceDrawer({ source, onClose }: Props) {
  const [data, setData] = useState<SourceWindow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!source) {
      setData(null)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getSource({
        book: source.book_title,
        chapter: source.chapter_index,
        start: source.char_start ?? undefined,
        end: source.char_end ?? undefined,
        excerpt: source.excerpt,
      })
      .then((win) => {
        if (!cancelled) setData(win)
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
  }, [source])

  if (!source) return null

  return (
    <aside className="source-drawer" role="dialog" aria-label="原文">
      <header className="source-drawer-header">
        <div>
          <strong>原文</strong>
          <div className="hint">
            《{source.book_title}》{data?.chapter_title ?? `第${source.chapter_index}章`}
          </div>
        </div>
        <button type="button" className="btn-link" onClick={onClose}>
          关闭
        </button>
      </header>
      <div className="source-drawer-body">
        {loading && <p className="hint">加载原文…</p>}
        {error && <p className="error-inline">{error}</p>}
        {data && (
          <>
            {data.degraded && <p className="hint">仅摘录 / 定位降级</p>}
            <pre className="source-text">
              {data.highlight ? (
                <>
                  {data.text.slice(0, data.highlight.start)}
                  <mark>{data.text.slice(data.highlight.start, data.highlight.end)}</mark>
                  {data.text.slice(data.highlight.end)}
                </>
              ) : (
                data.text || source.excerpt
              )}
            </pre>
          </>
        )}
      </div>
    </aside>
  )
}
