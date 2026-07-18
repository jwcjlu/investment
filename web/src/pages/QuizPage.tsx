import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import type { QuizResponse, QuizSubmitResponse } from '../api'
import Layout, { ErrorBlock, LoadingBlock } from './Layout'

export default function QuizPage() {
  const [searchParams] = useSearchParams()
  const encodedTag = searchParams.get('tag') ?? undefined
  const isDaily = searchParams.get('daily') === '1'

  const [quiz, setQuiz] = useState<QuizResponse | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<QuizSubmitResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!encodedTag && !isDaily) {
      setError('缺少 tag 或 daily 参数')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    setResult(null)
    setAnswers({})
    api
      .getQuiz({ tag: encodedTag, daily: isDaily })
      .then((data) => {
        if (!cancelled) setQuiz(data)
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
  }, [encodedTag, isDaily])

  function selectAnswer(questionId: string, index: number) {
    if (result) return
    setAnswers((prev) => ({ ...prev, [questionId]: index }))
  }

  const allAnswered = useMemo(
    () => !!quiz && quiz.questions.every((q) => answers[q.id] !== undefined),
    [quiz, answers],
  )

  async function handleSubmit() {
    if (!quiz) return
    setSubmitting(true)
    setError(null)
    try {
      const data = await api.submitQuiz(quiz.tag, answers)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const breadcrumb = (
    <>
      <Link to="/">首页</Link>
      {quiz && (
        <>
          {' / '}
          <Link to={`/module/${quiz.encoded_tag}`}>{quiz.tag}</Link>
          {' / 小测'}
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

  if (!quiz) {
    return (
      <Layout breadcrumb={breadcrumb}>
        <ErrorBlock message={error ?? '题库不存在'} />
      </Layout>
    )
  }

  const detailMap = new Map((result?.details ?? []).map((d) => [d.id, d]))

  return (
    <Layout breadcrumb={breadcrumb}>
      <h1>「{quiz.tag}」小测</h1>
      {quiz.source === 'placeholder' && (
        <p className="hint">（占位题库，未调用 AI 生成）</p>
      )}
      {error && <ErrorBlock message={error} />}

      {result && (
        <section className="quiz-score">
          得分：{result.score} / {quiz.questions.length}
        </section>
      )}

      <div className="quiz-list">
        {quiz.questions.map((q, qi) => {
          const detail = detailMap.get(q.id)
          return (
            <section key={q.id} className="quiz-question">
              <h3>
                {qi + 1}. {q.stem}
              </h3>
              <div className="quiz-options">
                {q.options.map((opt, oi) => {
                  const selected = answers[q.id] === oi
                  const classes = ['quiz-option']
                  if (selected) classes.push('is-selected')
                  if (detail) {
                    if (oi === q.answer_index) classes.push('is-correct')
                    else if (selected) classes.push('is-wrong')
                  }
                  return (
                    <label key={oi} className={classes.join(' ')}>
                      <input
                        type="radio"
                        name={q.id}
                        checked={selected}
                        disabled={!!result}
                        onChange={() => selectAnswer(q.id, oi)}
                      />
                      {opt}
                    </label>
                  )
                })}
              </div>
              {detail && (
                <p className={`quiz-explanation ${detail.correct ? 'is-correct' : 'is-wrong'}`}>
                  {detail.correct ? '✅ 答对了。' : '❌ 答错了。'} {detail.explanation}
                </p>
              )}
            </section>
          )
        })}
      </div>

      {!result ? (
        <button
          type="button"
          className="btn-primary"
          onClick={handleSubmit}
          disabled={!allAnswered || submitting}
        >
          {submitting ? '提交中…' : '提交答案'}
        </button>
      ) : (
        <Link className="btn-secondary" to={`/module/${quiz.encoded_tag}`}>
          返回模块 →
        </Link>
      )}
    </Layout>
  )
}
