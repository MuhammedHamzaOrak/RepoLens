import { useEffect, useState } from 'react'
import { askProject } from '../api/client'
import type { ChatResponse } from '../types/api'

interface ChatPanelProps {
  projectId: string
  disabled: boolean
  onSelectSource: (chunkId: string) => void
}

interface Exchange {
  id: number
  question: string
  response: ChatResponse
}

function AnswerContent({ answer }: { answer: string }) {
  return (
    <div className="answer-content">
      {answer.split('```').map((part, index) => {
        if (index % 2 === 0) {
          return part.trim() ? <p key={index}>{part.trim()}</p> : null
        }
        const [firstLine, ...remainingLines] = part.replace(/^\n/, '').split('\n')
        const hasLanguageLabel = /^[a-zA-Z0-9_+-]+$/.test(firstLine.trim())
        const code = hasLanguageLabel ? remainingLines.join('\n') : part
        return <pre key={index}><code>{code.trim()}</code></pre>
      })}
    </div>
  )
}

export default function ChatPanel({
  projectId,
  disabled,
  onSelectSource,
}: ChatPanelProps) {
  const [question, setQuestion] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [isAsking, setIsAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setQuestion('')
    setExchanges([])
    setError(null)
  }, [projectId])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedQuestion = question.trim()
    if (!normalizedQuestion || disabled || isAsking) return

    setIsAsking(true)
    setError(null)
    try {
      const response = await askProject(projectId, normalizedQuestion)
      setExchanges((current) => [
        ...current,
        { id: Date.now(), question: normalizedQuestion, response },
      ])
      setQuestion('')
    } catch (askError) {
      setError(askError instanceof Error ? askError.message : 'Yanıt oluşturulamadı.')
    } finally {
      setIsAsking(false)
    }
  }

  return (
    <section className="workspace-section chat-section" aria-labelledby="chat-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">GROUNDED CHAT</p>
          <h3 id="chat-title">Projeye soru sor</h3>
        </div>
        <span className="privacy-note">Veriler cihazından çıkmaz</span>
      </div>

      {exchanges.length === 0 ? (
        <div className="chat-empty">
          <span className="chat-empty__icon" aria-hidden="true">?</span>
          <div>
            <strong>Kod hakkında ne öğrenmek istiyorsun?</strong>
            <p>Örneğin: “Kullanıcı kaydı nerede uygulanıyor?”</p>
          </div>
        </div>
      ) : (
        <div className="conversation" aria-live="polite">
          {exchanges.map((exchange) => (
            <article className="exchange" key={exchange.id}>
              <div className="question-bubble">{exchange.question}</div>
              <div className={`answer-block answer-block--${exchange.response.answer_status}`}>
                <div className="answer-block__label">
                  <span aria-hidden="true">RL</span>
                  <strong>
                    {exchange.response.answer_status === 'grounded'
                      ? 'Kaynaklı yanıt'
                      : 'Yetersiz bağlam'}
                  </strong>
                </div>
                <AnswerContent answer={exchange.response.answer} />
                {exchange.response.sources.length > 0 ? (
                  <div className="source-cards">
                    {exchange.response.sources.map((source, index) => (
                      <button
                        className="source-card"
                        type="button"
                        key={source.chunk_id}
                        onClick={() => onSelectSource(source.chunk_id)}
                      >
                        <span className="source-card__number">{index + 1}</span>
                        <span>
                          <strong>{source.file_path}</strong>
                          <small>
                            {source.symbol_name ?? source.symbol_type} · satır {source.start_line}–{source.end_line}
                          </small>
                        </span>
                        <span className="source-card__arrow" aria-hidden="true">→</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}

      {error ? <p className="form-message form-message--error" role="alert">{error}</p> : null}
      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea
          aria-label="Proje hakkında soru"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={disabled ? 'Soru sormak için önce projeyi indeksle.' : 'Kod tabanı hakkında bir soru yaz...'}
          disabled={disabled || isAsking}
          rows={2}
        />
        <button
          className="button button--primary chat-submit"
          type="submit"
          disabled={disabled || isAsking || !question.trim()}
        >
          {isAsking ? <><span className="spinner" /> Yanıtlanıyor</> : <>Sor <span aria-hidden="true">→</span></>}
        </button>
      </form>
    </section>
  )
}
