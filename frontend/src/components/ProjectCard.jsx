import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const STEP_NAMES = ['', '벤치마킹', '대본', '음성+자막', '스토리보드', '이미지+영상', '편집', '썸네일', '업로드']
const STEP_ICONS = ['', '🔍', '📝', '🎙️', '🎬', '🖼️', '✂️', '🎨', '🚀']

export default function ProjectCard({ project, onDelete }) {
  const navigate = useNavigate()
  const [hovered, setHovered] = useState(false)
  const step = project.current_step || 0
  const pct = Math.round((step / 8) * 100)

  const isCompleted = step >= 8
  const isNotStarted = !step || step === 0
  const accentColor = isCompleted ? '#10B981' : isNotStarted ? '#8A9BBF' : '#5B78F6'
  const gradientBar = isCompleted
    ? 'linear-gradient(90deg, #10B981, #34D399)'
    : isNotStarted
    ? 'linear-gradient(90deg, #253550, #253550)'
    : 'linear-gradient(90deg, #5B78F6, #8B5CF6)'

  const statusLabel = isCompleted ? '완료' : isNotStarted ? '시작 전' : `Step ${step} · ${STEP_NAMES[step]}`
  const statusBg = isCompleted ? 'rgba(16,185,129,0.12)' : isNotStarted ? 'rgba(74,84,112,0.12)' : 'rgba(91,120,246,0.12)'

  const formattedDate = new Date(project.created_at).toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', year: 'numeric',
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
        background: '#111A2E',
        border: `1px solid ${hovered ? accentColor + '40' : '#253550'}`,
        borderRadius: 16,
        cursor: 'pointer',
        transition: 'all 0.2s',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? `0 8px 32px rgba(0,0,0,0.4)` : 'none',
        overflow: 'hidden',
      }}
    >
      {/* Top gradient bar */}
      <div style={{ height: 3, background: gradientBar }} />

      <div style={{ padding: 16 }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
          {/* Step icon */}
          <div style={{
            width: 34, height: 34, borderRadius: 9, flexShrink: 0,
            background: `${accentColor}18`,
            border: `1px solid ${accentColor}30`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>
            {isCompleted ? '✅' : isNotStarted ? '🎬' : STEP_ICONS[step] || '🎬'}
          </div>

          {/* Title + date */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{
              fontSize: 14, fontWeight: 600, color: '#E8EEFF',
              margin: '0 0 3px', lineHeight: 1.35,
              overflow: 'hidden', textOverflow: 'ellipsis',
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            }}>
              {project.title}
            </h2>
            <span style={{ fontSize: 11, color: '#8A9BBF' }}>{formattedDate}</span>
          </div>

          {/* Status badge (top right) + delete */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <span style={{
              fontSize: 11, fontWeight: 500, padding: '3px 8px',
              borderRadius: 6, background: statusBg, color: accentColor,
              whiteSpace: 'nowrap',
            }}>
              {isCompleted ? '완료' : isNotStarted ? '시작 전' : `${step}/8`}
            </span>
            <button
              className="delete-btn"
              onClick={handleDelete}
              style={{
                width: 26, height: 26, borderRadius: 6,
                border: 'none', background: 'transparent',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#8A9BBF', opacity: hovered ? 1 : 0,
                transition: 'opacity 0.15s, background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.12)'
                e.currentTarget.style.color = '#EF4444'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = '#8A9BBF'
              }}
            >
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        {/* Current step label */}
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: accentColor }}>
            {statusLabel}
          </span>
          <span style={{ fontSize: 11, color: '#8A9BBF', marginLeft: 8 }}>{pct}%</span>
        </div>

        {/* Progress bar */}
        <div style={{ height: 4, background: '#172336', borderRadius: 4, marginBottom: 8, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4,
            background: gradientBar,
            width: `${pct}%`,
            transition: 'width 0.5s ease',
          }} />
        </div>

        {/* Step dots */}
        <div style={{ display: 'flex', gap: 3 }}>
          {Array.from({ length: 8 }, (_, i) => (
            <div
              key={i}
              style={{
                flex: 1, height: 3, borderRadius: 2,
                background: i < step ? accentColor : '#253550',
                transition: 'background 0.3s',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
