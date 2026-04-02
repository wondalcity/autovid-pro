import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getProjects, createProject, deleteProject } from '../lib/api'
import ProjectCard from '../components/ProjectCard'

const PIPELINE_STEPS = [
  { num: 1, icon: '🔍', name: '벤치마킹' },
  { num: 2, icon: '📝', name: '대본' },
  { num: 3, icon: '🎙️', name: '음성+자막' },
  { num: 4, icon: '🎬', name: '스토리보드' },
  { num: 5, icon: '🖼️', name: '이미지+영상' },
  { num: 6, icon: '✂️', name: '편집' },
  { num: 7, icon: '🎨', name: '썸네일' },
  { num: 8, icon: '🚀', name: '업로드' },
]

const GENRE_OPTIONS = [
  { value: 'general',  label: '일반 범용',      icon: '🎯' },
  { value: 'finance',  label: '금융/비즈니스',   icon: '💹' },
  { value: 'mystery',  label: '미스터리/흥미',   icon: '🔮' },
  { value: 'history',  label: '역사/다큐',       icon: '📜' },
]
const TONE_OPTIONS = [
  { value: 'professional',  label: '전문적' },
  { value: 'friendly',      label: '친근한' },
  { value: 'educational',   label: '교육적' },
  { value: 'entertainment', label: '엔터테인먼트' },
]
const DURATION_OPTIONS = [
  { value: '5',  label: '5분' },
  { value: '10', label: '10분 (권장)' },
  { value: '15', label: '15분' },
  { value: '20', label: '20분' },
]
const PRIVACY_OPTIONS = [
  { value: 'public',   label: '공개' },
  { value: 'unlisted', label: '미등록' },
  { value: 'private',  label: '비공개' },
]

const DEFAULT_SETTINGS = { keyword: '', genre: 'general', tone: 'professional', target_duration: '10', privacy: 'public' }

function saveProjectDefaults(projectId, settings) {
  try { localStorage.setItem(`autovid-defaults-${projectId}`, JSON.stringify(settings)) } catch {}
}

/* ── Shared field label ─────────────────────────────────────────────── */
function FieldLabel({ children, sub }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
        {children}
      </label>
      {sub && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-3)', textTransform: 'none', letterSpacing: 0, marginLeft: 6 }}>{sub}</span>}
    </div>
  )
}

/* ── Option button (pill/chip style) ───────────────────────────────── */
function OptionBtn({ active, onClick, children, style }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '7px 12px',
        borderRadius: 'var(--radius-sm)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        background: active ? 'var(--accent-dim)' : 'transparent',
        color: active ? 'var(--text)' : 'var(--text-2)',
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        cursor: 'pointer',
        transition: 'all 0.15s',
        textAlign: 'left',
        fontFamily: 'var(--font)',
        ...style,
      }}
    >
      {children}
    </button>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS })
  const [modalStep, setModalStep] = useState(1)

  const resetModal = () => { setNewTitle(''); setSettings({ ...DEFAULT_SETTINGS }); setModalStep(1) }

  const fetchProjects = async () => {
    try {
      setLoading(true)
      const res = await getProjects()
      setProjects(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProjects() }, [])

  const handleCreate = async () => {
    if (!newTitle.trim() || creating) return
    try {
      setCreating(true)
      const res = await createProject(newTitle.trim())
      const projectId = res.data?.id
      if (projectId) {
        saveProjectDefaults(projectId, { ...settings, keyword: settings.keyword || newTitle.trim() })
      }
      resetModal()
      setShowCreate(false)
      await fetchProjects()
    } catch (err) {
      console.error(err)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteProject(id)
      await fetchProjects()
    } catch (err) {
      console.error(err)
    }
  }

  const inProgress = projects.filter(p => p.current_step > 0 && p.current_step < 8)
  const completed  = projects.filter(p => p.current_step >= 8)
  const notStarted = projects.filter(p => !p.current_step || p.current_step === 0)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '0 28px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: 1200, margin: '0 auto' }}>

          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 36, borderRadius: 9,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, flexShrink: 0, color: '#fff',
            }}>▶</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.3px', lineHeight: 1.2 }}>AutoVidPro</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.2, fontWeight: 400 }}>AI YouTube 자동화</div>
            </div>
          </div>

          {/* Right actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="nav-btn"
              onClick={() => navigate('/settings')}
              style={{ padding: '0 14px', height: 38, fontSize: 13 }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
              </svg>
              설정
            </button>

            <button
              className="btn-primary"
              onClick={() => setShowCreate(true)}
              style={{ padding: '0 16px', height: 38, fontSize: 13 }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              새 프로젝트
            </button>
          </div>
        </div>
      </header>

      {/* ── Create modal ─────────────────────────────────────────────── */}
      {showCreate && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(12, 28, 60, 0.48)',
            backdropFilter: 'blur(12px)',
          }}
          onClick={e => { if (e.target === e.currentTarget) { setShowCreate(false); resetModal() } }}
        >
          <div className="slide-up" style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-xl)',
            padding: '28px',
            width: '100%', maxWidth: 480,
            boxShadow: '0 24px 80px rgba(12,28,60,0.2)',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 32, height: 36, borderRadius: 9,
                  background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
                }}>🎬</div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.3px' }}>새 프로젝트</div>
                  <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 1 }}>설정값은 각 단계에 자동 적용됩니다</div>
                </div>
              </div>
              {/* Step dots */}
              <div style={{ display: 'flex', gap: 5 }}>
                {[1, 2].map(n => (
                  <div key={n} style={{
                    width: 20, height: 3, borderRadius: 2,
                    background: modalStep >= n ? 'var(--accent)' : 'var(--border)',
                    transition: 'background 0.2s',
                  }} />
                ))}
              </div>
            </div>

            {/* Step 1 */}
            {modalStep === 1 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }} className="fade-in">
                <div>
                  <FieldLabel>프로젝트 제목 <span style={{ color: 'var(--red)' }}>*</span></FieldLabel>
                  <input
                    autoFocus
                    type="text"
                    value={newTitle}
                    onChange={e => setNewTitle(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && newTitle.trim()) setModalStep(2)
                      if (e.key === 'Escape') { setShowCreate(false); resetModal() }
                    }}
                    placeholder="예: ETF 투자 완전 가이드 2025"
                    style={{
                      width: '100%', background: 'var(--surface-3)',
                      border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                      padding: '10px 13px', fontSize: 14, color: 'var(--text)',
                      outline: 'none', fontFamily: 'var(--font)', transition: 'border-color 0.15s',
                    }}
                    onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>
                <div>
                  <FieldLabel sub="Step 1 벤치마킹에 사용">검색 키워드 / 주제</FieldLabel>
                  <input
                    type="text"
                    value={settings.keyword}
                    onChange={e => setSettings(s => ({ ...s, keyword: e.target.value }))}
                    onKeyDown={e => { if (e.key === 'Enter' && newTitle.trim()) setModalStep(2) }}
                    placeholder="예: ETF 투자 방법, 주식 초보 가이드"
                    style={{
                      width: '100%', background: 'var(--surface-3)',
                      border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                      padding: '10px 13px', fontSize: 14, color: 'var(--text)',
                      outline: 'none', fontFamily: 'var(--font)', transition: 'border-color 0.15s',
                    }}
                    onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                    onBlur={e => e.target.style.borderColor = 'var(--border)'}
                  />
                  <p style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 5 }}>비워두면 프로젝트 제목이 키워드로 사용됩니다</p>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button
                    onClick={() => { setShowCreate(false); resetModal() }}
                    className="nav-btn"
                    style={{ flex: 1, height: 44, justifyContent: 'center', fontSize: 13 }}
                  >
                    취소
                  </button>
                  <button
                    onClick={() => setModalStep(2)}
                    disabled={!newTitle.trim()}
                    className="btn-primary"
                    style={{ flex: 2, height: 44, justifyContent: 'center', fontSize: 13, opacity: !newTitle.trim() ? 0.4 : 1, cursor: !newTitle.trim() ? 'not-allowed' : 'pointer' }}
                  >
                    다음 — 콘텐츠 설정 →
                  </button>
                </div>
              </div>
            )}

            {/* Step 2 */}
            {modalStep === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }} className="fade-in">
                {/* Genre */}
                <div>
                  <FieldLabel sub="Step 5 이미지 스타일에 반영">콘텐츠 장르</FieldLabel>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    {GENRE_OPTIONS.map(g => (
                      <OptionBtn key={g.value} active={settings.genre === g.value} onClick={() => setSettings(s => ({ ...s, genre: g.value }))}>
                        <span style={{ marginRight: 6 }}>{g.icon}</span>{g.label}
                      </OptionBtn>
                    ))}
                  </div>
                </div>

                {/* Tone + Duration */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <FieldLabel sub="Step 2 대본에 반영">말투 스타일</FieldLabel>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {TONE_OPTIONS.map(t => (
                        <OptionBtn key={t.value} active={settings.tone === t.value} onClick={() => setSettings(s => ({ ...s, tone: t.value }))}>
                          {t.label}
                        </OptionBtn>
                      ))}
                    </div>
                  </div>
                  <div>
                    <FieldLabel sub="Step 2 대본에 반영">영상 길이</FieldLabel>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {DURATION_OPTIONS.map(d => (
                        <OptionBtn key={d.value} active={settings.target_duration === d.value} onClick={() => setSettings(s => ({ ...s, target_duration: d.value }))}>
                          {d.label}
                        </OptionBtn>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Privacy */}
                <div>
                  <FieldLabel sub="Step 8 업로드에 반영">업로드 공개 설정</FieldLabel>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {PRIVACY_OPTIONS.map(p => (
                      <OptionBtn key={p.value} active={settings.privacy === p.value} onClick={() => setSettings(s => ({ ...s, privacy: p.value }))} style={{ flex: 1, textAlign: 'center' }}>
                        {p.label}
                      </OptionBtn>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button onClick={() => setModalStep(1)} className="nav-btn" style={{ height: 44, padding: '0 16px', fontSize: 13 }}>
                    ← 이전
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={creating}
                    className="btn-primary"
                    style={{ flex: 1, height: 44, justifyContent: 'center', fontSize: 13, opacity: creating ? 0.6 : 1 }}
                  >
                    {creating ? '생성 중…' : '🚀 프로젝트 생성'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Main ─────────────────────────────────────────────────────── */}
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '0 28px 80px' }}>

        {/* Hero */}
        <div style={{ padding: '52px 0 36px', textAlign: 'center' }}>
          <h1 style={{
            fontSize: 42, fontWeight: 800, letterSpacing: '-1.2px', lineHeight: 1.15,
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            backgroundClip: 'text', margin: '0 0 10px',
          }}>
            YouTube 영상, 8단계로 자동 완성
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text-2)', margin: '0 0 32px', lineHeight: 1.7, fontWeight: 400 }}>
            벤치마킹부터 YouTube 업로드까지 — AI가 전 과정을 자동화합니다
          </p>

          {/* Pipeline pills */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexWrap: 'wrap', gap: 0, marginBottom: projects.length > 0 ? 28 : 0,
          }}>
            {PIPELINE_STEPS.map((s, idx) => (
              <div key={s.num} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 20, padding: '5px 11px',
                  fontSize: 12, fontWeight: 500, color: 'var(--text-2)',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ fontSize: 13 }}>{s.icon}</span>
                  {s.name}
                </div>
                {idx < PIPELINE_STEPS.length - 1 && (
                  <div style={{ width: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
                      <path d="M2 5h6M6 2l3 3-3 3" stroke="var(--text-3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Stats */}
          {projects.length > 0 && !loading && (
            <div style={{
              display: 'inline-flex',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              overflow: 'hidden',
            }}>
              {[
                { label: '전체', value: projects.length, color: 'var(--accent)' },
                { label: '진행 중', value: inProgress.length, color: 'var(--amber)' },
                { label: '완료', value: completed.length, color: 'var(--green)' },
              ].map((stat, i) => (
                <div key={i} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  padding: '10px 24px',
                  borderRight: i < 2 ? '1px solid var(--border)' : 'none',
                }}>
                  <span style={{ fontSize: 22, fontWeight: 700, color: stat.color, letterSpacing: '-0.5px', lineHeight: 1 }}>{stat.value}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 3, fontWeight: 500, letterSpacing: '0.3px', textTransform: 'uppercase' }}>{stat.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: 14 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                height: 150, borderRadius: 'var(--radius-lg)',
                background: 'var(--surface)', border: '1px solid var(--border)',
                animation: 'pulse-dot 1.5s ease-in-out infinite',
              }} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '72px 0', textAlign: 'center' }}>
            <div style={{
              width: 64, height: 64, borderRadius: 18, marginBottom: 18,
              background: 'var(--surface-2)', border: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28,
            }}>🎬</div>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)', margin: '0 0 8px', letterSpacing: '-0.3px' }}>첫 프로젝트를 만들어보세요</h2>
            <p style={{ fontSize: 14, color: 'var(--text-2)', margin: '0 0 24px', lineHeight: 1.7 }}>
              벤치마킹부터 YouTube 업로드까지 8단계 자동화
            </p>
            <button
              className="btn-primary"
              onClick={() => setShowCreate(true)}
              style={{ padding: '0 22px', height: 46, fontSize: 14 }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              새 프로젝트 시작
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 36 }}>
            {[
              { label: '진행 중', items: inProgress, dot: 'var(--amber)' },
              { label: '시작 전', items: notStarted, dot: 'var(--text-3)' },
              { label: '완료',   items: completed,  dot: 'var(--green)' },
            ].filter(g => g.items.length > 0).map(group => (
              <section key={group.label}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: group.dot, flexShrink: 0 }} />
                  <h2 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', margin: 0, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                    {group.label} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>({group.items.length})</span>
                  </h2>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: 12 }}>
                  {group.items.map(p => <ProjectCard key={p.id} project={p} onDelete={handleDelete} />)}
                </div>
              </section>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
