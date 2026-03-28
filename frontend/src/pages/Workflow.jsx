import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProjects } from '../lib/api'
import StepCard from '../components/StepCard'

const STEPS = [
  { num: 1, name: '벤치마킹',     icon: '🔍', desc: '경쟁 영상 분석' },
  { num: 2, name: '대본',         icon: '📝', desc: '씬 기반 대본 작성' },
  { num: 3, name: '음성 + 자막',  icon: '🎙️', desc: 'TTS + SRT 생성' },
  { num: 4, name: '스토리보드',   icon: '🎬', desc: '씬 구성 기획' },
  { num: 5, name: '이미지 + 영상', icon: '🖼️', desc: 'AI 이미지·영상 생성' },
  { num: 6, name: '편집',         icon: '✂️', desc: 'FFmpeg 최종 편집' },
  { num: 7, name: '썸네일',       icon: '🎨', desc: 'AI 썸네일 생성' },
  { num: 8, name: '업로드',       icon: '🚀', desc: 'YouTube 자동 업로드' },
]

const STATUS_COLOR = { pending: '#8A9BBF', running: '#F59E0B', done: '#10B981', error: '#EF4444' }
const STATUS_LABEL = { pending: '대기', running: '실행 중', done: '완료', error: '오류' }
const STATUS_BG    = { pending: 'rgba(74,84,112,0.15)', running: 'rgba(245,158,11,0.15)', done: 'rgba(16,185,129,0.15)', error: 'rgba(239,68,68,0.15)' }

function loadProjectDefaults(projectId) {
  try { return JSON.parse(localStorage.getItem(`autovid-defaults-${projectId}`) || '{}') }
  catch { return {} }
}

export default function Workflow() {
  const { projectId } = useParams()
  const navigate      = useNavigate()
  const [project, setProject]           = useState(null)
  const [activeStep, setActiveStep]     = useState(1)
  const [statuses, setStatuses]         = useState({})
  const [projectDefaults, setProjectDefaults] = useState({})

  useEffect(() => {
    setProjectDefaults(loadProjectDefaults(projectId))
    getProjects().then(res => {
      const p = res.data.find(x => x.id === projectId)
      if (!p) return
      setProject(p)
      const cur = p.current_step || 0
      const st  = {}
      STEPS.forEach(s => {
        if (s.num < cur)        st[s.num] = 'done'
        else if (s.num === cur) st[s.num] = 'running'
        else                    st[s.num] = 'pending'
      })
      setStatuses(st)
      // If pipeline is fully complete (step 9+), show the final video (step 6)
      const defaultStep = cur >= 9 ? 6 : Math.max(1, Math.min(cur || 1, 8))
      setActiveStep(defaultStep)
    }).catch(console.error)
  }, [projectId])

  const onStatusChange = useCallback((num, s) => {
    setStatuses(prev => ({ ...prev, [num]: s }))
  }, [])

  const done = Object.values(statuses).filter(s => s === 'done').length
  const pct  = Math.round((done / 8) * 100)
  const aStep = STEPS.find(s => s.num === activeStep)

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100vh',
      background: '#080B12', color: '#E8EEFF', overflow: 'hidden',
      fontFamily: 'inherit',
    }}>

      {/* Header — 56px */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: 16,
        padding: '0 24px', height: 56, flexShrink: 0,
        background: '#0C1018', borderBottom: '1px solid #253550',
      }}>
        {/* Back button */}
        <button
          onClick={() => navigate('/')}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'none', border: 'none', color: '#A8B6CB',
            fontSize: 13, cursor: 'pointer', padding: '5px 10px',
            borderRadius: 8, flexShrink: 0, transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = '#172336'; e.currentTarget.style.color = '#E8EEFF' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#A8B6CB' }}
        >
          <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          대시보드
        </button>

        {/* Vertical divider */}
        <div style={{ width: 1, height: 20, background: '#253550', flexShrink: 0 }} />

        {/* Project title */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{
            fontSize: 14, fontWeight: 600, color: '#E8EEFF',
            display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {project?.title || '로딩 중...'}
          </span>
        </div>

        {/* Progress pill */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
          background: '#111A2E', border: '1px solid #253550',
          borderRadius: 20, padding: '4px 14px 4px 10px',
        }}>
          <div style={{ width: 160, height: 6, background: '#253550', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 6,
              background: 'linear-gradient(90deg, #5B78F6, #8B5CF6)',
              width: `${pct}%`, transition: 'width 0.5s ease',
            }} />
          </div>
          <span style={{ fontSize: 12, color: '#A8B6CB', whiteSpace: 'nowrap', fontWeight: 500 }}>
            {done}/8 완료
          </span>
        </div>
      </header>

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar — 260px */}
        <aside style={{
          width: 260, flexShrink: 0,
          background: '#0C1018', borderRight: '1px solid #253550',
          overflowY: 'auto', padding: '12px 10px',
        }}>
          {STEPS.map((step, idx) => {
            const s      = statuses[step.num] || 'pending'
            const active = activeStep === step.num
            const color  = STATUS_COLOR[s]
            const bg     = STATUS_BG[s]

            return (
              <div key={step.num} style={{ position: 'relative' }}>
                {/* Connector line between steps */}
                {idx < STEPS.length - 1 && (
                  <div style={{
                    position: 'absolute',
                    left: 30, top: 52, width: 2, height: 10, zIndex: 0,
                    background: s === 'done' ? '#10B981' : '#253550',
                    transition: 'background 0.3s',
                  }} />
                )}

                <button
                  onClick={() => setActiveStep(step.num)}
                  style={{
                    position: 'relative', zIndex: 1,
                    display: 'flex', alignItems: 'center', gap: 12,
                    width: '100%', padding: '8px 10px', marginBottom: 2,
                    background: active ? 'rgba(91,120,246,0.12)' : 'transparent',
                    border: `1px solid ${active ? 'rgba(91,120,246,0.35)' : 'transparent'}`,
                    borderRadius: 12, cursor: 'pointer', textAlign: 'left',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
                  onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
                >
                  {/* Status circle — 36x36 */}
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
                    background: bg,
                    border: `2px solid ${color}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, transition: 'border-color 0.3s',
                  }}>
                    {s === 'done'
                      ? <span style={{ color: '#10B981', fontSize: 14, fontWeight: 700 }}>✓</span>
                      : s === 'running'
                      ? <span className="animate-pulse" style={{ color: '#F59E0B', fontSize: 10 }}>●</span>
                      : s === 'error'
                      ? <span style={{ color: '#EF4444', fontSize: 12, fontWeight: 700 }}>!</span>
                      : <span style={{ color: '#8A9BBF', fontSize: 11, fontWeight: 600 }}>{step.num}</span>
                    }
                  </div>

                  {/* Step name + status */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, fontWeight: 600,
                      color: active ? '#E8EEFF' : s === 'done' ? '#A8B6CB' : '#8898B5',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      marginBottom: 2,
                    }}>
                      {step.name}
                    </div>
                    <div style={{
                      fontSize: 11,
                      color: active ? '#5B78F6' : color,
                    }}>
                      {STATUS_LABEL[s]}
                    </div>
                  </div>
                </button>
              </div>
            )
          })}
        </aside>

        {/* Main content */}
        <main style={{
          flex: 1, overflowY: 'auto',
          padding: '32px 40px',
          background: '#080B12',
        }}>
          {aStep && (
            <StepCard
              step={aStep}
              projectId={projectId}
              status={statuses[activeStep] || 'pending'}
              onStatusChange={onStatusChange}
              projectDefaults={projectDefaults}
            />
          )}
        </main>
      </div>
    </div>
  )
}
