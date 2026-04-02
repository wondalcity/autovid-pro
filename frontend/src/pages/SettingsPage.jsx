import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSettings, saveSettings } from '../lib/api'

const SECTIONS = [
  {
    title: 'AI 텍스트 생성',
    icon: '🧠',
    color: '#7B54F0',
    fields: [
      {
        key: 'ANTHROPIC_API_KEY',
        label: 'Anthropic API Key',
        hint: 'Claude — 대본 생성, 스토리보드, 프롬프트 향상',
        link: 'https://console.anthropic.com/',
        linkText: 'console.anthropic.com',
        secret: true,
      },
      {
        key: 'OPENAI_API_KEY',
        label: 'OpenAI API Key',
        hint: 'DALL-E 3 이미지 생성 및 GPT 폴백',
        link: 'https://platform.openai.com/api-keys',
        linkText: 'platform.openai.com',
        secret: true,
      },
    ],
  },
  {
    title: '이미지 생성',
    icon: '🖼️',
    color: '#4B78F5',
    fields: [
      {
        key: 'IMAGE_PROVIDER',
        label: '기본 이미지 제공자',
        hint: 'auto = 사용 가능한 제공자를 순서대로 시도',
        secret: false,
        select: ['auto', 'dalle3', 'gemini', 'stabilityai'],
        selectLabels: { auto: '자동 (권장)', dalle3: 'DALL-E 3 (OpenAI)', gemini: 'Gemini Imagen (Google)', stabilityai: 'Stability AI' },
      },
      {
        key: 'GOOGLE_AI_API_KEY',
        label: 'Google AI API Key',
        hint: 'Gemini Imagen 이미지 생성',
        link: 'https://aistudio.google.com/app/apikey',
        linkText: 'aistudio.google.com',
        secret: true,
      },
      {
        key: 'STABLE_DIFFUSION_API_KEY',
        label: 'Stability AI API Key',
        hint: 'Stable Diffusion Core 이미지 생성',
        link: 'https://platform.stability.ai/account/keys',
        linkText: 'platform.stability.ai',
        secret: true,
      },
    ],
  },
  {
    title: '음성 합성 (TTS)',
    icon: '🎙️',
    color: '#22C55E',
    fields: [
      {
        key: 'ELEVENLABS_API_KEY',
        label: 'ElevenLabs API Key',
        hint: '나레이션 음성 생성 (Step 3)',
        link: 'https://elevenlabs.io/app/settings/api-keys',
        linkText: 'elevenlabs.io',
        secret: true,
      },
      {
        key: 'ELEVENLABS_DEFAULT_VOICE_ID',
        label: 'Voice ID',
        hint: '기본 음성 ID (기본값: 21m00Tcm4TlvDq8ikWAM — Rachel)',
        secret: false,
        placeholder: '21m00Tcm4TlvDq8ikWAM',
      },
    ],
  },
  {
    title: '영상 생성',
    icon: '🎬',
    color: '#F59E0B',
    fields: [
      {
        key: 'RUNWAY_API_KEY',
        label: 'Runway ML API Key',
        hint: 'AI 영상 생성 (Step 5)',
        link: 'https://app.runwayml.com/',
        linkText: 'app.runwayml.com',
        secret: true,
      },
    ],
  },
  {
    title: '배경 음악',
    icon: '🎵',
    color: '#EC4899',
    fields: [
      {
        key: 'PIXABAY_API_KEY',
        label: 'Pixabay API Key',
        hint: 'CC0 저작권 무료 배경음악 다운로드 (Step 6)',
        link: 'https://pixabay.com/api/docs/',
        linkText: 'pixabay.com/api',
        secret: true,
      },
    ],
  },
  {
    title: 'YouTube',
    icon: '▶️',
    color: '#EF4444',
    fields: [
      {
        key: 'YOUTUBE_API_KEY',
        label: 'YouTube Data API Key',
        hint: '경쟁 영상 검색 및 분석 (Step 1)',
        link: 'https://console.cloud.google.com/',
        linkText: 'console.cloud.google.com',
        secret: true,
      },
    ],
  },
]

function SelectField({ value, onChange, options, labels }) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value || 'auto'}
        onChange={e => onChange(e.target.value)}
        style={{
          width: '100%', background: 'var(--surface-3)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
          padding: '9px 36px 9px 13px', fontSize: 14, color: 'var(--text)',
          outline: 'none', cursor: 'pointer', appearance: 'none',
          fontFamily: 'var(--font)', transition: 'border-color 0.15s',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--border)'}
      >
        {options.map(opt => (
          <option key={opt} value={opt} style={{ background: 'var(--surface-2)' }}>
            {labels?.[opt] || opt}
          </option>
        ))}
      </select>
      <svg style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--text-3)' }}
        width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  )
}

function SecretInput({ value, placeholder, onChange }) {
  const [revealed, setRevealed] = useState(false)
  const [inputVal, setInputVal] = useState('')

  const isMasked = value && value.startsWith('••')
  const displayVal = inputVal !== '' ? inputVal : (isMasked ? '' : (value || ''))

  return (
    <div style={{ position: 'relative' }}>
      <input
        type={revealed ? 'text' : 'password'}
        value={displayVal}
        placeholder={isMasked ? value : (placeholder || '키를 입력하세요…')}
        onChange={e => { setInputVal(e.target.value); onChange(e.target.value) }}
        style={{
          width: '100%', background: 'var(--surface-3)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
          padding: '9px 42px 9px 13px', fontSize: 14, color: 'var(--text)',
          outline: 'none', fontFamily: 'var(--font)',
          transition: 'border-color 0.15s', letterSpacing: revealed ? 0 : '0.05em',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--border)'}
      />
      <button
        type="button"
        onClick={() => setRevealed(r => !r)}
        style={{
          position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-3)', padding: 4, borderRadius: 4,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'color 0.15s',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-2)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}
        title={revealed ? '숨기기' : '보기'}
      >
        {revealed ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  )
}

function TextInput({ value, placeholder, onChange }) {
  return (
    <input
      type="text"
      value={value || ''}
      placeholder={placeholder || '값을 입력하세요…'}
      onChange={e => onChange(e.target.value)}
      style={{
        width: '100%', background: 'var(--surface-3)',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
        padding: '9px 13px', fontSize: 14, color: 'var(--text)',
        outline: 'none', fontFamily: 'var(--font)', transition: 'border-color 0.15s',
      }}
      onFocus={e => e.target.style.borderColor = 'var(--accent)'}
      onBlur={e => e.target.style.borderColor = 'var(--border)'}
    />
  )
}

export default function SettingsPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState({})
  const [pending, setPending] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings()
      .then(res => setSettings(res.data.settings || {}))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleChange = (key, value) => setPending(p => ({ ...p, [key]: value }))

  const handleSave = async () => {
    if (saving || Object.keys(pending).length === 0) return
    setSaving(true)
    try {
      const res = await saveSettings(pending)
      setSettings(res.data.settings || {})
      setPending({})
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = Object.keys(pending).length > 0

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center',
        background: 'var(--surface)', borderBottom: '1px solid var(--border)',
        padding: '0 28px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: 800, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button className="nav-btn" onClick={() => navigate('/')} style={{ padding: '0 12px', height: 36, fontSize: 13 }}>
              <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7"/>
              </svg>
              대시보드
            </button>
            <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.2px' }}>API 키 설정</span>
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            style={{
              padding: '0 16px', height: 36, fontSize: 13, fontWeight: 600,
              borderRadius: 'var(--radius-sm)', border: 'none', cursor: hasChanges ? 'pointer' : 'not-allowed',
              background: saved ? 'var(--green)' : hasChanges ? 'var(--accent)' : 'var(--surface-3)',
              color: hasChanges || saved ? '#fff' : 'var(--text-3)',
              transition: 'all 0.2s', fontFamily: 'var(--font)',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {saved ? (
              <><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>저장됨</>
            ) : saving ? '저장 중…' : hasChanges ? '저장' : '저장됨'}
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 800, margin: '0 auto', padding: '36px 28px 80px' }}>

        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.5px', margin: '0 0 6px' }}>API 키 설정</h1>
          <p style={{ fontSize: 14, color: 'var(--text-2)', lineHeight: 1.7, fontWeight: 400 }}>
            각 서비스의 API 키를 입력하면 AutoVidPro가 자동으로 사용합니다.
            키는 서버에 저장되며 .env 파일보다 우선 적용됩니다.
          </p>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                height: 110, borderRadius: 'var(--radius-lg)',
                background: 'var(--surface)', border: '1px solid var(--border)',
                animation: 'pulse-dot 1.5s ease-in-out infinite',
              }} />
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {SECTIONS.map(section => (
              <div
                key={section.title}
                style={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  overflow: 'hidden',
                }}
              >
                {/* Section header */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '12px 18px',
                  borderBottom: '1px solid var(--border)',
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 'var(--radius-xs)',
                    background: `${section.color}18`,
                    border: `1px solid ${section.color}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14,
                  }}>
                    {section.icon}
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '0.2px' }}>
                    {section.title}
                  </span>
                </div>

                {/* Fields */}
                <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {section.fields.map(field => {
                    const currentVal = pending[field.key] !== undefined
                      ? pending[field.key]
                      : (settings[field.key] || '')
                    const isSet = settings[field.key] && settings[field.key] !== ''

                    return (
                      <div key={field.key}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '0.3px', textTransform: 'uppercase' }}>
                            {field.label}
                          </label>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{
                              fontSize: 12, fontWeight: 600, letterSpacing: '0.2px',
                              padding: '2px 7px', borderRadius: 4,
                              background: isSet ? 'var(--green-dim)' : 'var(--amber-dim)',
                              color: isSet ? 'var(--green)' : 'var(--amber)',
                            }}>
                              {isSet ? '설정됨' : '미설정'}
                            </span>
                            {field.link && (
                              <a href={field.link} target="_blank" rel="noreferrer"
                                style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none', fontWeight: 500 }}>
                                {field.linkText} ↗
                              </a>
                            )}
                          </div>
                        </div>

                        {field.select ? (
                          <SelectField
                            value={currentVal}
                            options={field.select}
                            labels={field.selectLabels}
                            onChange={v => handleChange(field.key, v)}
                          />
                        ) : field.secret ? (
                          <SecretInput
                            value={currentVal}
                            placeholder={field.placeholder}
                            onChange={v => handleChange(field.key, v)}
                          />
                        ) : (
                          <TextInput
                            value={currentVal}
                            placeholder={field.placeholder}
                            onChange={v => handleChange(field.key, v)}
                          />
                        )}

                        <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '5px 0 0', lineHeight: 1.5 }}>
                          {field.hint}
                        </p>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Bottom save */}
        {!loading && (
          <div style={{ marginTop: 28, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="btn-primary"
              style={{
                padding: '0 24px', height: 44, fontSize: 14,
                opacity: !hasChanges && !saved ? 0.4 : 1,
                background: saved ? 'var(--green)' : undefined,
                cursor: hasChanges ? 'pointer' : 'not-allowed',
              }}
            >
              {saved ? (
                <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>저장 완료</>
              ) : saving ? '저장 중…' : '변경사항 저장'}
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
