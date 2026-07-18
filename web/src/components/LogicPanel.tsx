import { useEffect, useMemo, useState } from 'react'
import * as api from '../api'
import type { LogicStructure, SourceRef } from '../api'

type Props = {
  encodedId: string
  encodedTag: string
  onOpenSource: (ref: SourceRef) => void
}

export default function LogicPanel({ encodedId, encodedTag, onOpenSource }: Props) {
  const [logic, setLogic] = useState<LogicStructure | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .getLessonLogic(encodedId, encodedTag)
      .then((data) => {
        if (!cancelled) setLogic(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [encodedId, encodedTag])

  const nodeMap = useMemo(() => {
    const m = new Map<string, LogicStructure['nodes'][number]>()
    for (const n of logic?.nodes ?? []) m.set(n.node_id, n)
    return m
  }, [logic])

  if (error) return <p className="hint">逻辑结构加载失败：{error}</p>
  if (!logic) return <p className="hint">整理逻辑结构中…</p>

  return (
    <section className="logic-panel">
      <h2>
        逻辑结构 <span className="hint">({logic.source})</span>
      </h2>
      <div className="logic-grid">
        <div className="logic-layers">
          {logic.layers.map((layer) => (
            <div key={layer.level} className={`logic-layer level-${layer.level}`}>
              <div className="logic-layer-title">
                L{layer.level} {layer.title}
              </div>
              <ul>
                {layer.items.map((item) => {
                  const node = nodeMap.get(item.node_id)
                  if (!node) return null
                  const clickable = !node.ungrounded && node.sources?.[0]
                  return (
                    <li key={item.node_id}>
                      {clickable ? (
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => onOpenSource(node.sources[0])}
                        >
                          {node.label}
                        </button>
                      ) : (
                        node.label
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
        <div className="logic-graph">
          <div className="logic-layer-title">关系图</div>
          {logic.edges.length === 0 ? (
            <p className="hint">暂无关系图</p>
          ) : (
            <ul className="edge-list">
              {logic.edges.map((e) => {
                const from = nodeMap.get(e.from)?.label ?? e.from
                const to = nodeMap.get(e.to)?.label ?? e.to
                return (
                  <li key={e.edge_id}>
                    <button
                      type="button"
                      className="btn-link"
                      disabled={!!e.ungrounded}
                      onClick={() => {
                        const n = nodeMap.get(e.from) || nodeMap.get(e.to)
                        if (n?.sources?.[0]) onOpenSource(n.sources[0])
                      }}
                    >
                      {from} —{e.rel}→ {to}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
