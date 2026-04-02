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

const STATUS_COLOR = { pending: 'var(--text-3)', running: 'var(--amber)', done: 'var(--green)', error: 'var(--red)' }
const STATUS_LABEL = { pending: '대기', running: '실행 중', done: '완료', error: '오류' }
const STATUS_BG    = { pending: 'transparent', running: 'var(--amber-dim)', done: 'var(--green-dim)', error: 'var(--red-dim)' }

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
      background: 'var(--bg)', color: 'var(--text)', overflow: 'hidden',
    }}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '0 22px', height: 54, flexShrink: 0,
        background: 'var(--surface)', borderBottom: '1px solid var(--border)',
      }}>
        <button
          onClick={() => navigate('/')}
          className="nav-btn"
          style={{ padding: '0 12px', height: 36, fontSize: 13, flexShrink: 0 }}
        >
          <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          대시보드
        </button>

        <div style={{ width: 1, height: 16, background: 'var(--border)', flexShrink: 0 }} />

        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{
            fontSize: 14, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.2px',
            display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {project?.title || '로딩 중...'}
          </span>
        </div>

        {/* Progress */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 20, padding: '4px 14px 4px 12px',
        }}>
          <div style={{ width: 140, height: 4, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 4,
              background: 'linear-gradient(90deg, var(--accent), var(--accent-2))',
              width: `${pct}%`, transition: 'width 0.5s ease',
            }} />
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap', fontWeight: 500 }}>
            {done}/8 완료
          </span>
        </div>
      </header>

      {/* ── Body ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar */}
        <aside style={{
          width: 248, flexShrink: 0,
          background: 'var(--surface)', borderRight: '1px solid var(--border)',
          overflowY: 'auto', padding: '10px 8px',
        }}>
          {STEPS.map((step, idx) => {
            const s      = statuses[step.num] || 'pending'
            const active = activeStep === step.num
            const color  = STATUS_COLOR[s]

            return (
              <div key={step.num} style={{ position: 'relative' }}>
                {idx < STEPS.length - 1 && (
                  <div style={{
                    position: 'absolute',
                    left: 27, top: 50, width: 1, height: 10, zIndex: 0,
                    background: s === 'done' ? 'var(--green)' : 'var(--border)',
                    transition: 'background 0.3s',
                  }} />
                )}

                <button
                  onClick={() => setActiveStep(step.num)}
                  style={{
                    position: 'relative', zIndex: 1,
                    display: 'flex', alignItems: 'center', gap: 10,
                    width: '100%', padding: '7px 9px', marginBottom: 1,
                    background: active ? 'var(--accent-dim)' : 'transparent',
                    border: `1px solid ${active ? 'var(--accent-border)' : 'transparent'}`,
                    borderRadius: 'var(--radius-sm)', cursor: 'pointer', textAlign: 'left',
                    transition: 'all 0.15s', fontFamily: 'var(--font)',
                  }}
                  onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--surface-2)' }}
                  onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
                >
                  {/* Status circle */}
                  <div style={{
                    width: 32, height: 36, borderRadius: '50%', flexShrink: 0,
                    background: STATUS_BG[s],
                    border: `1.5px solid ${color}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, transition: 'border-color 0.3s',
                  }}>
                    {s === 'done'
                      ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth={2.5} strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                      : s === 'running'
                      ? <span className="pulse-dot" style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--amber)', display: 'block' }} />
                      : s === 'error'
                      ? <span style={{ color: 'var(--red)', fontSize: 14, fontWeight: 700, lineHeight: 1 }}>!</span>
                      : <span style={{ color: 'var(--text-3)', fontSize: 12, fontWeight: 600 }}>{step.num}</span>
                    }
                  </div>

                  {/* Text */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, fontWeight: active ? 600 : 500,
                      color: active ? 'var(--text)' : s === 'done' ? 'var(--text-2)' : 'var(--text-2)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      marginBottom: 1, letterSpacing: '-0.1px',
                    }}>
                      {step.name}
                    </div>
                    <div style={{ fontSize: 12, color: active ? 'var(--accent)' : color, fontWeight: 500 }}>
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
          padding: '28px 36px',
          background: 'var(--bg)',
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
