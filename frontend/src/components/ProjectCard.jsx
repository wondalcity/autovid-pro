import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const STEP_NAMES = ['', '벤치마킹', '대본', '음성+자막', '스토리보드', '이미지+영상', '편집', '썸네일', '업로드']
const STEP_ICONS = ['', '🔍', '📝', '🎙️', '🎬', '🖼️', '✂️', '🎨', '🚀']

const STATE = {
  completed:  { accent: 'var(--green)',  bg: 'var(--green-dim)',  border: 'var(--green-border)',  grad: 'linear-gradient(90deg, var(--green), #4ADE80)' },
  notStarted: { accent: 'var(--text-3)', bg: 'transparent',       border: 'var(--border)',        grad: 'var(--border)' },
  active:     { accent: 'var(--accent)', bg: 'var(--accent-dim)', border: 'var(--accent-border)', grad: 'linear-gradient(90deg, var(--accent), var(--accent-2))' },
}

export default function ProjectCard({ project, onDelete }) {
  const navigate = useNavigate()
  const [hovered, setHovered] = useState(false)
  const step = project.current_step || 0
  const pct  = Math.round((step / 8) * 100)

  const isCompleted  = step >= 8
  const isNotStarted = !step || step === 0
  const C = isCompleted ? STATE.completed : isNotStarted ? STATE.notStarted : STATE.active

  const statusLabel = isCompleted ? '완료' : isNotStarted ? '시작 전' : `Step ${step} · ${STEP_NAMES[step]}`
  const badgeLabel  = isCompleted ? '완료' : isNotStarted ? '미시작' : `${step}/8`

  const formattedDate = new Date(project.created_at).toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'short', day: 'numeric',
  })

  const handleDelete = (e) => {
    e.stopPropagation()
    if (window.confirm(`"${project.title}" 프로젝트를 삭제하시겠습니까?`)) {
      onDelete(project.id)
    }
  }

  return (
    <div
      onClick={() => navigate(`/workflow/${project.id}`)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        background: 'var(--surface)',
        border: `1px solid ${hovered ? C.border : 'var(--border)'}`,
        borderRadius: 'var(--radius-lg)',
        cursor: 'pointer',
        transition: 'border-color 0.18s, box-shadow 0.18s, transform 0.18s',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? 'var(--shadow-lg)' : 'var(--shadow-sm)',
        overflow: 'hidden',
      }}
    >
      {/* Top accent bar */}
      <div style={{ height: 3, background: C.grad, opacity: isNotStarted ? 0.4 : 1 }} />

      <div style={{ padding: '14px 16px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 11, marginBottom: 14 }}>
          {/* Icon */}
          <div style={{
            width: 34, height: 34, borderRadius: 9, flexShrink: 0,
            background: C.bg,
            border: `1px solid ${C.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>
            {isCompleted ? '✅' : isNotStarted ? '🎬' : STEP_ICONS[step] || '🎬'}
          </div>

          {/* Title + date */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="truncate-2" style={{
              fontSize: 14, fontWeight: 600, color: 'var(--text)',
              margin: '0 0 3px', lineHeight: 1.4, letterSpacing: '-0.1px',
            }}>
              {project.title}
            </h2>
            <span style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 400 }}>{formattedDate}</span>
          </div>

          {/* Badge + delete */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
            <span style={{
              fontSize: 12, fontWeight: 600, padding: '3px 7px', borderRadius: 5,
              background: C.bg, color: C.accent,
              border: `1px solid ${C.border}`,
              whiteSpace: 'nowrap', letterSpacing: '0.2px',
            }}>
              {badgeLabel}
            </span>
            <button
              onClick={handleDelete}
              style={{
                width: 26, height: 26, borderRadius: 6,
                border: 'none', background: 'transparent',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--text-3)', opacity: hovered ? 1 : 0,
                transition: 'opacity 0.15s, background 0.15s, color 0.15s',
                flexShrink: 0,
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--red-dim)'; e.currentTarget.style.color = 'var(--red)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-3)' }}
              title="삭제"
            >
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Status + percent */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.accent }}>{statusLabel}</span>
          {!isNotStarted && <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{pct}%</span>}
        </div>

        {/* Progress bar */}
        <div style={{ height: 4, background: 'var(--surface-2)', borderRadius: 4, overflow: 'hidden', marginBottom: 7 }}>
          <div style={{
            height: '100%', borderRadius: 4, background: C.grad,
            width: `${pct}%`, transition: 'width 0.5s ease',
          }} />
        </div>

        {/* Step segments */}
        <div style={{ display: 'flex', gap: 2 }}>
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} style={{
              flex: 1, height: 2, borderRadius: 2,
              background: i < step ? C.accent : 'var(--border)',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>
      </div>
    </div>
  )
}
