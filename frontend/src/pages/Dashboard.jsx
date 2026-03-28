import { useState, useEffect } from 'react'
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
  { value: 'general',  label: '일반 범용',        icon: '🎯' },
  { value: 'finance',  label: '금융/비즈니스',     icon: '💹' },
  { value: 'mystery',  label: '미스터리/흥미',     icon: '🔮' },
  { value: 'history',  label: '역사/다큐',         icon: '📜' },
]
const TONE_OPTIONS = [
  { value: 'professional',   label: '전문적' },
  { value: 'friendly',       label: '친근한' },
  { value: 'educational',    label: '교육적' },
  { value: 'entertainment',  label: '엔터테인먼트' },
]
const DURATION_OPTIONS = [
  { value: '5',  label: '5분' },
  { value: '10', label: '10분 (권장)' },
  { value: '15', label: '15분' },
  { value: '20', label: '20분' },
]
const PRIVACY_OPTIONS = [
  { value: 'public',    label: '공개' },
  { value: 'unlisted',  label: '미등록' },
  { value: 'private',   label: '비공개' },
]

const DEFAULT_SETTINGS = { keyword: '', genre: 'general', tone: 'professional', target_duration: '10', privacy: 'public' }

function saveProjectDefaults(projectId, settings) {
  try { localStorage.setItem(`autovid-defaults-${projectId}`, JSON.stringify(settings)) } catch {}
}

export default function Dashboard() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS })
  const [modalStep, setModalStep] = useState(1) // 1=title+keyword, 2=settings

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
        const defaults = { ...settings, keyword: settings.keyword || newTitle.trim() }
        saveProjectDefaults(projectId, defaults)
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
  const completed = projects.filter(p => p.current_step >= 8)
  const notStarted = projects.filter(p => !p.current_step || p.current_step === 0)

  return (
    <div style={{ minHeight: '100vh', background: '#080B12', color: '#E8EEFF', fontFamily: 'inherit' }}>

      {/* Sticky Nav */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 60, display: 'flex', alignItems: 'center',
        background: '#0C1018',
        borderBottom: '1px solid #253550',
        padding: '0 32px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: 1200, margin: '0 auto' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 10,
              background: 'linear-gradient(135deg, #5B78F6, #8B5CF6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 15, flexShrink: 0,
            }}>▶</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#E8EEFF', lineHeight: 1.2 }}>AutoVidPro</div>
              <div style={{ fontSize: 11, color: '#8A9BBF', lineHeight: 1.2 }}>AI 기반 YouTube 영상 자동화</div>
            </div>
          </div>

          {/* New project button */}
          <button
            onClick={() => setShowCreate(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: '#5B78F6', color: 'white',
              border: 'none', borderRadius: 10, cursor: 'pointer',
              padding: '0 18px', height: 38, fontSize: 13, fontWeight: 600,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#6B88FF'}
            onMouseLeave={e => e.currentTarget.style.background = '#5B78F6'}
          >
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
            새 프로젝트
          </button>
        </div>
      </header>

      {/* Create project modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(8,11,18,0.88)',
          backdropFilter: 'blur(8px)',
        }}
          onClick={e => { if (e.target === e.currentTarget) { setShowCreate(false); resetModal() } }}
        >
          <div style={{
            background: '#111A2E', border: '1px solid #253550',
            borderRadius: 18, padding: '28px',
            width: '100%', maxWidth: 500,
            boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
          }}>
            {/* Modal header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
              <div style={{ width: 34, height: 34, borderRadius: 10, background: 'linear-gradient(135deg, #5B78F6, #8B5CF6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>🎬</div>
              <div style={{ flex: 1 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#E8EEFF', margin: 0 }}>새 프로젝트 만들기</h3>
                <p style={{ fontSize: 11, color: '#8A9BBF', margin: '2px 0 0' }}>설정값은 각 단계의 기본값으로 자동 채워집니다</p>
              </div>
              {/* Step indicator */}
              <div style={{ display: 'flex', gap: 4 }}>
                {[1, 2].map(n => (
                  <div key={n} style={{ width: 22, height: 4, borderRadius: 2, background: modalStep >= n ? '#5B78F6' : '#253550', transition: 'background 0.2s' }} />
                ))}
              </div>
            </div>

            {/* Step 1: Title + Keyword */}
            {modalStep === 1 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                    프로젝트 제목 <span style={{ color: '#EF4444' }}>*</span>
                  </label>
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
                    style={{ width: '100%', background: '#172336', border: '1px solid #253550', borderRadius: 12, padding: '12px 14px', fontSize: 14, color: '#E8EEFF', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.15s' }}
                    onFocus={e => e.target.style.borderColor = '#5B78F6'}
                    onBlur={e => e.target.style.borderColor = '#253550'}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                    검색 키워드 / 주제
                    <span style={{ fontSize: 10, fontWeight: 400, textTransform: 'none', color: '#4A6080', marginLeft: 6 }}>Step 1 벤치마킹에 사용</span>
                  </label>
                  <input
                    type="text"
                    value={settings.keyword}
                    onChange={e => setSettings(s => ({ ...s, keyword: e.target.value }))}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && newTitle.trim()) setModalStep(2)
                    }}
                    placeholder="예: ETF 투자 방법, 주식 초보 가이드"
                    style={{ width: '100%', background: '#172336', border: '1px solid #253550', borderRadius: 12, padding: '12px 14px', fontSize: 13, color: '#E8EEFF', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.15s' }}
                    onFocus={e => e.target.style.borderColor = '#5B78F6'}
                    onBlur={e => e.target.style.borderColor = '#253550'}
                  />
                  <p style={{ fontSize: 11, color: '#4A6080', margin: '6px 0 0' }}>비워두면 프로젝트 제목이 키워드로 사용됩니다</p>
                </div>
                <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                  <button onClick={() => { setShowCreate(false); resetModal() }}
                    style={{ flex: 1, height: 42, borderRadius: 10, border: '1px solid #253550', background: '#172336', color: '#A8B6CB', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>
                    취소
                  </button>
                  <button onClick={() => setModalStep(2)} disabled={!newTitle.trim()}
                    style={{ flex: 2, height: 42, borderRadius: 10, border: 'none', background: !newTitle.trim() ? '#253550' : '#5B78F6', color: !newTitle.trim() ? '#8A9BBF' : 'white', fontSize: 13, fontWeight: 600, cursor: !newTitle.trim() ? 'not-allowed' : 'pointer' }}>
                    다음 — 콘텐츠 설정 →
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Content settings */}
            {modalStep === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                {/* Genre */}
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 10 }}>
                    콘텐츠 장르
                    <span style={{ fontSize: 10, fontWeight: 400, textTransform: 'none', color: '#4A6080', marginLeft: 6 }}>Step 5 이미지 스타일에 반영</span>
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {GENRE_OPTIONS.map(g => (
                      <button key={g.value} onClick={() => setSettings(s => ({ ...s, genre: g.value }))}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 10, border: `1px solid ${settings.genre === g.value ? '#5B78F6' : '#253550'}`, background: settings.genre === g.value ? 'rgba(91,120,246,0.12)' : '#172336', color: settings.genre === g.value ? '#E8EEFF' : '#A8B6CB', fontSize: 12, fontWeight: 500, cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s' }}>
                        <span style={{ fontSize: 16 }}>{g.icon}</span>
                        {g.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tone + Duration side by side */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                      말투 스타일
                      <span style={{ display: 'block', fontSize: 10, fontWeight: 400, textTransform: 'none', color: '#4A6080', marginTop: 1 }}>Step 2 대본에 반영</span>
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {TONE_OPTIONS.map(t => (
                        <button key={t.value} onClick={() => setSettings(s => ({ ...s, tone: t.value }))}
                          style={{ padding: '7px 11px', borderRadius: 8, border: `1px solid ${settings.tone === t.value ? '#5B78F6' : '#253550'}`, background: settings.tone === t.value ? 'rgba(91,120,246,0.12)' : 'transparent', color: settings.tone === t.value ? '#5B78F6' : '#8A9BBF', fontSize: 12, fontWeight: 500, cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s' }}>
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                      목표 영상 길이
                      <span style={{ display: 'block', fontSize: 10, fontWeight: 400, textTransform: 'none', color: '#4A6080', marginTop: 1 }}>Step 2 대본에 반영</span>
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {DURATION_OPTIONS.map(d => (
                        <button key={d.value} onClick={() => setSettings(s => ({ ...s, target_duration: d.value }))}
                          style={{ padding: '7px 11px', borderRadius: 8, border: `1px solid ${settings.target_duration === d.value ? '#5B78F6' : '#253550'}`, background: settings.target_duration === d.value ? 'rgba(91,120,246,0.12)' : 'transparent', color: settings.target_duration === d.value ? '#5B78F6' : '#8A9BBF', fontSize: 12, fontWeight: 500, cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s' }}>
                          {d.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Privacy */}
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#8A9BBF', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>
                    업로드 공개 설정
                    <span style={{ fontSize: 10, fontWeight: 400, textTransform: 'none', color: '#4A6080', marginLeft: 6 }}>Step 8 업로드에 반영</span>
                  </label>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {PRIVACY_OPTIONS.map(p => (
                      <button key={p.value} onClick={() => setSettings(s => ({ ...s, privacy: p.value }))}
                        style={{ flex: 1, padding: '8px', borderRadius: 8, border: `1px solid ${settings.privacy === p.value ? '#5B78F6' : '#253550'}`, background: settings.privacy === p.value ? 'rgba(91,120,246,0.12)' : 'transparent', color: settings.privacy === p.value ? '#5B78F6' : '#8A9BBF', fontSize: 12, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s' }}>
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                  <button onClick={() => setModalStep(1)}
                    style={{ height: 42, padding: '0 18px', borderRadius: 10, border: '1px solid #253550', background: '#172336', color: '#A8B6CB', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>
                    ← 이전
                  </button>
                  <button onClick={handleCreate} disabled={creating}
                    style={{ flex: 1, height: 42, borderRadius: 10, border: 'none', background: creating ? '#253550' : 'linear-gradient(135deg, #5B78F6, #8B5CF6)', color: creating ? '#8A9BBF' : 'white', fontSize: 13, fontWeight: 700, cursor: creating ? 'not-allowed' : 'pointer' }}>
                    {creating ? '생성 중...' : '🚀 프로젝트 생성'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '0 32px 64px' }}>

        {/* Hero section */}
        <div style={{ padding: '56px 0 40px', textAlign: 'center' }}>
          <h1 style={{
            fontSize: 40, fontWeight: 800, color: '#E8EEFF',
            background: 'linear-gradient(135deg, #E8EEFF 0%, #8B5CF6 60%, #5B78F6 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            backgroundClip: 'text', margin: '0 0 12px', lineHeight: 1.15,
          }}>
            YouTube 영상, 8단계로 자동 완성
          </h1>
          <p style={{ fontSize: 15, color: '#A8B6CB', margin: '0 0 36px', lineHeight: 1.6 }}>
            벤치마킹부터 YouTube 업로드까지 — AI가 전 과정을 자동화합니다
          </p>

          {/* Pipeline step pills */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexWrap: 'wrap', gap: 0, marginBottom: projects.length > 0 ? 36 : 0,
          }}>
            {PIPELINE_STEPS.map((s, idx) => (
              <div key={s.num} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  background: '#111A2E', border: '1px solid #253550',
                  borderRadius: 20, padding: '6px 12px',
                  fontSize: 12, fontWeight: 500, color: '#A8B6CB',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ fontSize: 13 }}>{s.icon}</span>
                  <span>{s.name}</span>
                </div>
                {idx < PIPELINE_STEPS.length - 1 && (
                  <div style={{ width: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path d="M2 5h6M6 2l3 3-3 3" stroke="#253550" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Stats strip — only when projects exist */}
          {projects.length > 0 && !loading && (
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 0,
              background: '#111A2E', border: '1px solid #253550',
              borderRadius: 12, overflow: 'hidden',
            }}>
              {[
                { label: '전체', value: projects.length, color: '#5B78F6' },
                { label: '진행 중', value: inProgress.length, color: '#F59E0B' },
                { label: '완료', value: completed.length, color: '#10B981' },
              ].map((stat, i) => (
                <div key={i} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  padding: '12px 28px',
                  borderRight: i < 2 ? '1px solid #253550' : 'none',
                }}>
                  <span style={{ fontSize: 22, fontWeight: 700, color: stat.color, lineHeight: 1 }}>{stat.value}</span>
                  <span style={{ fontSize: 11, color: '#8A9BBF', marginTop: 4 }}>{stat.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                height: 160, borderRadius: 16, background: '#111A2E',
                border: '1px solid #253550',
              }} className="animate-pulse" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 0', textAlign: 'center' }}>
            <div style={{
              width: 72, height: 72, borderRadius: 20, marginBottom: 20,
              background: '#111A2E', border: '1px solid #253550',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 32,
            }}>🎬</div>
            <h2 style={{ fontSize: 22, fontWeight: 700, color: '#E8EEFF', margin: '0 0 10px' }}>첫 프로젝트를 만들어보세요</h2>
            <p style={{ fontSize: 14, color: '#8A9BBF', margin: '0 0 28px', lineHeight: 1.6 }}>
              벤치마킹부터 YouTube 업로드까지 8단계 자동화
            </p>
            <button
              onClick={() => setShowCreate(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: '#5B78F6', color: 'white',
                border: 'none', borderRadius: 10, cursor: 'pointer',
                padding: '0 22px', height: 44, fontSize: 14, fontWeight: 600,
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#6B88FF'}
              onMouseLeave={e => e.currentTarget.style.background = '#5B78F6'}
            >
              <span style={{ fontSize: 18 }}>+</span> 새 프로젝트 시작
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>

            {inProgress.length > 0 && (
              <section>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#F59E0B', flexShrink: 0 }} />
                  <h2 style={{ fontSize: 12, fontWeight: 600, color: '#A8B6CB', margin: 0, letterSpacing: '0.5px' }}>
                    진행 중 ({inProgress.length})
                  </h2>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                  {inProgress.map(p => <ProjectCard key={p.id} project={p} onDelete={handleDelete} />)}
                </div>
              </section>
            )}

            {notStarted.length > 0 && (
              <section>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#8A9BBF', flexShrink: 0 }} />
                  <h2 style={{ fontSize: 12, fontWeight: 600, color: '#A8B6CB', margin: 0, letterSpacing: '0.5px' }}>
                    시작 전 ({notStarted.length})
                  </h2>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                  {notStarted.map(p => <ProjectCard key={p.id} project={p} onDelete={handleDelete} />)}
                </div>
              </section>
            )}

            {completed.length > 0 && (
              <section>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', flexShrink: 0 }} />
                  <h2 style={{ fontSize: 12, fontWeight: 600, color: '#A8B6CB', margin: 0, letterSpacing: '0.5px' }}>
                    완료 ({completed.length})
                  </h2>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
                  {completed.map(p => <ProjectCard key={p.id} project={p} onDelete={handleDelete} />)}
                </div>
              </section>
            )}

          </div>
        )}
      </main>
    </div>
  )
}
