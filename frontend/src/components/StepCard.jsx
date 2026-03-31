import { useState, useEffect, useRef, useCallback } from 'react'
import { runStep, getStepStatus, getStepData, approveScript, cancelStep } from '../lib/api'

// ── Step metadata ──────────────────────────────────────────────────────────────
const STEP_META = {
  1: {
    desc: 'URL을 직접 입력하거나 키워드만 입력하면 조회수 상위 영상을 자동으로 찾아 분석합니다.',
    manualInputs: [
      { key: 'keyword', label: '검색 키워드', placeholder: '예: ETF 투자 방법, 주식 초보 가이드', type: 'text', hint: 'URL 없을 때 자동 검색에 사용됩니다' },
      { key: 'youtube_urls', label: 'YouTube URL 직접 입력', placeholder: 'https://www.youtube.com/watch?v=abc123\nhttps://youtu.be/def456', type: 'textarea', hint: '한 줄에 하나씩 (선택사항)' },
    ],
    autoOptions: [
      { key: 'max_results', label: '자동 검색 영상 수', type: 'select', options: ['3', '5', '10'], optionLabels: ['3개', '5개 (권장)', '10개'], default: '5' },
      { key: 'region', label: '검색 지역', type: 'select', options: ['KR', 'US', 'global'], optionLabels: ['한국', '미국', '전체'], default: 'KR' },
    ],
  },
  2: {
    desc: '벤치마킹 분석 데이터를 바탕으로 PD AI가 기획서와 씬 기반 대본을 작성합니다.',
    manualInputs: [
      { key: 'story_concept', label: '스토리 컨셉 (선택사항)', placeholder: '예: "초보자를 위한 ETF 투자 가이드" — 비워두면 AI가 자동으로 결정합니다', type: 'textarea' },
    ],
    autoOptions: [
      { key: 'target_duration', label: '목표 영상 길이', type: 'select', options: ['5', '10', '15', '20'], optionLabels: ['5분', '10분 (권장)', '15분', '20분'], default: '10' },
      { key: 'tone', label: '말투 스타일', type: 'select', options: ['professional', 'friendly', 'educational', 'entertainment'], optionLabels: ['전문적', '친근한', '교육적', '엔터테인먼트'], default: 'professional' },
      { key: 'scene_count', label: '씬 수', type: 'select', options: ['5', '8', '12'], optionLabels: ['5개', '8개 (권장)', '12개'], default: '8' },
    ],
  },
  3: {
    desc: '확정된 대본을 ElevenLabs TTS로 음성 변환하고 Whisper로 자막 파일을 자동 생성합니다.',
    manualInputs: [
      { key: 'voice_id', label: 'ElevenLabs Voice ID', placeholder: '비워두면 기본 목소리 사용', type: 'text', hint: 'ElevenLabs 콘솔에서 확인 가능' },
    ],
    autoOptions: [
      { key: 'stability', label: '음성 안정성', type: 'select', options: ['0.4', '0.6', '0.8'], optionLabels: ['낮음 (다이나믹)', '보통 (권장)', '높음 (안정적)'], default: '0.6' },
      { key: 'language', label: '자막 언어', type: 'select', options: ['ko', 'en', 'auto'], optionLabels: ['한국어', '영어', '자동 감지'], default: 'ko' },
    ],
  },
  4: {
    desc: '대본을 씬 단위로 분해하여 AI 이미지 생성을 위한 스토리보드를 구성합니다.',
    manualInputs: [],
    autoOptions: [
      { key: 'visual_style', label: '시각적 스타일', type: 'select', options: ['cinematic', 'clean', 'dynamic', 'minimal'], optionLabels: ['시네마틱', '클린/모던', '다이나믹', '미니멀'], default: 'cinematic' },
      { key: 'scene_duration', label: '씬당 기본 길이', type: 'select', options: ['5', '8', '10', '15'], optionLabels: ['5초', '8초 (권장)', '10초', '15초'], default: '8' },
    ],
  },
  5: {
    desc: '스토리보드의 각 씬에 맞는 이미지를 AI로 생성합니다. 크레딧 소진 시 다음 AI로 자동 전환됩니다.',
    manualInputs: [],
    autoOptions: [
      { key: 'image_provider', label: '이미지 AI', type: 'select', options: ['auto', 'dalle3', 'gemini', 'stabilityai'], optionLabels: ['자동 (크레딧 소진 시 전환)', 'DALL-E 3 (OpenAI)', 'Gemini Imagen 3 (Google)', 'Stability AI'], default: 'auto' },
      { key: 'genre', label: '이미지 스타일 장르', type: 'select', options: ['general', 'finance', 'mystery', 'history'], optionLabels: ['일반 (범용)', '금융/비즈니스', '미스터리', '역사/다큐'], default: 'general' },
    ],
  },
  6: {
    desc: 'FFmpeg으로 씬 클립을 이어붙이고 TTS 음성과 자막을 합쳐 최종 MP4를 만듭니다.',
    manualInputs: [
      { key: 'burn_subtitles', label: '자막 하드코딩 (Burn-in)', type: 'toggle', hint: '항상 자막이 보이게 영상에 직접 삽입합니다' },
    ],
    autoOptions: [
      { key: 'subtitle_style', label: '자막 스타일', type: 'select', options: ['white', 'yellow', 'auto'], optionLabels: ['흰색', '노란색', '자동'], default: 'auto' },
    ],
  },
  7: {
    desc: 'Strategist AI가 YouTube 제목과 경쟁 분석 데이터를 기반으로 썸네일을 생성합니다.',
    manualInputs: [],
    autoOptions: [
      { key: 'thumbnail_style', label: '썸네일 스타일', type: 'select', options: ['bold', 'minimal', 'gradient'], optionLabels: ['임팩트 (굵은 텍스트)', '미니멀/클린', '그라디언트'], default: 'bold' },
      { key: 'include_title_text', label: '제목 텍스트 포함', type: 'toggle', defaultChecked: true, hint: '썸네일에 제목 텍스트를 오버레이합니다' },
    ],
  },
  8: {
    desc: 'AI가 생성한 제목·설명·태그를 검토하고 수정한 뒤 YouTube에 업로드합니다.',
    manualInputs: [],
    autoOptions: [
      { key: 'privacy', label: '공개 설정', type: 'select', options: ['public', 'unlisted', 'private'], optionLabels: ['공개', '미등록', '비공개'], default: 'public' },
      { key: 'notify_subscribers', label: '구독자 알림', type: 'toggle', defaultChecked: false, hint: '업로드 시 구독자에게 알림을 보냅니다' },
    ],
  },
}

// ── Status config ──────────────────────────────────────────────────────────────
const STATUS = {
  pending:         { label: '대기 중',   color: '#8A9BBF', bg: 'rgba(74,84,112,0.15)' },
  running:         { label: '실행 중',   color: '#F59E0B', bg: 'rgba(245,158,11,0.15)' },
  done:            { label: '완료',      color: '#10B981', bg: 'rgba(16,185,129,0.15)' },
  error:           { label: '오류',      color: '#EF4444', bg: 'rgba(239,68,68,0.15)' },
  awaiting_review: { label: '검토 필요', color: '#A78BFA', bg: 'rgba(167,139,250,0.15)' },
}

// ── Input styles ───────────────────────────────────────────────────────────────
const inputStyle = {
  width: '100%', background: '#172336', border: '1px solid #253550',
  borderRadius: 12, padding: '11px 14px', fontSize: 13, color: '#E8EEFF',
  outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.15s',
  fontFamily: 'inherit',
}
const inputFocusStyle = { ...inputStyle, border: '1px solid #5B78F6' }

// ── Helper components ─────────────────────────────────────────────────────────
function Label({ children }) {
  return (
    <p style={{
      fontSize: 11, fontWeight: 600, color: '#8A9BBF',
      textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 10, margin: '0 0 10px',
    }}>
      {children}
    </p>
  )
}

function Card({ children, style: extraStyle = {} }) {
  return (
    <div style={{
      background: '#111A2E', border: '1px solid #253550',
      borderRadius: 14, padding: '16px 18px', ...extraStyle,
    }}>
      {children}
    </div>
  )
}

function Tag({ children, color = '#5B78F6' }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      fontSize: 11, fontWeight: 500, padding: '3px 8px',
      borderRadius: 6, background: `${color}18`, color,
    }}>
      {children}
    </span>
  )
}

// ── Step output renderers ──────────────────────────────────────────────────────
function StepOutput({ step, data }) {
  if (!data || Object.keys(data).length === 0) return null

  switch (step) {
    case 1: {
      const ar = data.analysis_result || {}
      const benchVideos = data.benchmarked_videos || []
      const keyFacts = data.key_facts || ar.key_facts || []
      if (!ar.competitive_summary && !ar.title_thumbnail_patterns && !benchVideos.length) return null

      // Helper: extract video ID from URL
      const getVideoId = (url) => {
        const m = url?.match(/(?:v=|\/embed\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/)
        return m ? m[1] : null
      }
      // Helper: format ISO datetime to KST readable
      const formatTime = (iso) => {
        if (!iso) return ''
        try {
          return new Date(iso).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        } catch { return '' }
      }

      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Timeline: Analysed Videos ───────────────────────────────── */}
          {benchVideos.length > 0 && (
            <Card>
              <Label>📹 분석 타임라인 ({benchVideos.length}개 영상)</Label>
              <div style={{ position: 'relative', marginTop: 8 }}>
                {/* Vertical line */}
                <div style={{
                  position: 'absolute', left: 16, top: 0, bottom: 0,
                  width: 2, background: 'linear-gradient(to bottom, #5B78F6, #1a2a4a)',
                  borderRadius: 2,
                }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {benchVideos.map((v, i) => {
                    const vid = getVideoId(v.url)
                    const thumb = vid ? `https://img.youtube.com/vi/${vid}/mqdefault.jpg` : null
                    const ytUrl = vid ? `https://www.youtube.com/watch?v=${vid}` : v.url
                    const excerpt = (v.transcript_excerpt || '').trim()
                    return (
                      <div key={i} style={{ display: 'flex', gap: 16, paddingBottom: 20, paddingLeft: 40, position: 'relative' }}>
                        {/* Timeline dot */}
                        <div style={{
                          position: 'absolute', left: 9, top: 4,
                          width: 16, height: 16, borderRadius: '50%',
                          background: '#5B78F6', border: '3px solid #0D1525',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 8, fontWeight: 700, color: 'white', flexShrink: 0,
                        }}>{i + 1}</div>

                        {/* Content */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          {/* Time badge */}
                          {v.created_at && (
                            <div style={{ fontSize: 11, color: '#5B78F6', marginBottom: 6, fontWeight: 500 }}>
                              🕐 {formatTime(v.created_at)} 분석
                            </div>
                          )}
                          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                            {/* Thumbnail */}
                            {thumb && (
                              <a href={ytUrl} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
                                <img
                                  src={thumb}
                                  alt={v.title}
                                  style={{ width: 100, height: 56, objectFit: 'cover', borderRadius: 6, display: 'block', border: '1px solid #253550' }}
                                  onError={e => { e.target.style.display = 'none' }}
                                />
                              </a>
                            )}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              {/* Title + open button */}
                              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 4 }}>
                                <span style={{ fontSize: 13, fontWeight: 600, color: '#E8EEFF', lineHeight: 1.4, flex: 1 }}>
                                  {v.title || v.url}
                                </span>
                                <a
                                  href={ytUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title="YouTube에서 열기"
                                  style={{ flexShrink: 0, color: '#5B78F6', display: 'flex', alignItems: 'center' }}
                                >
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
                                  </svg>
                                </a>
                              </div>
                              {/* Transcript excerpt */}
                              {excerpt && (
                                <p style={{ fontSize: 11, color: '#7A8FAD', lineHeight: 1.6, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                                  {excerpt}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </Card>
          )}

          {/* ── AI 전략 요약 ─────────────────────────────────────────────── */}
          {ar.competitive_summary && (
            <Card>
              <Label>🎯 전략 요약</Label>
              <p style={{ fontSize: 13, lineHeight: 1.7, color: '#C8D4F0', margin: 0 }}>{ar.competitive_summary}</p>
            </Card>
          )}

          {/* ── 핵심 팩트 ────────────────────────────────────────────────── */}
          {keyFacts.length > 0 && (
            <Card>
              <Label>💡 핵심 팩트</Label>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {keyFacts.map((f, i) => (
                  <li key={i} style={{ display: 'flex', gap: 10, fontSize: 13, alignItems: 'flex-start' }}>
                    <span style={{ color: '#5B78F6', fontWeight: 700, flexShrink: 0, lineHeight: 1.6 }}>0{i + 1}</span>
                    <span style={{ color: '#A8B6CB', lineHeight: 1.6 }}>{f}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* ── 제목·썸네일 패턴 + 추천 방향 ─────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
            {ar.title_thumbnail_patterns && (
              <Card>
                <Label>🏷️ 제목 · 썸네일 패턴</Label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                  {ar.title_thumbnail_patterns.patterns?.map((p, i) => <Tag key={i} color="#8B5CF6">{p}</Tag>)}
                </div>
                {ar.title_thumbnail_patterns.hook_words?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {ar.title_thumbnail_patterns.hook_words.map((w, i) => <Tag key={i} color="#5B78F6">{w}</Tag>)}
                  </div>
                )}
              </Card>
            )}
            {ar.suggested_angles?.length > 0 && (
              <Card>
                <Label>✨ 추천 콘텐츠 방향</Label>
                <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {ar.suggested_angles.map((a, i) => (
                    <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13 }}>
                      <span style={{ color: '#F59E0B', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                      <span style={{ color: '#A8B6CB', lineHeight: 1.5 }}>{a}</span>
                    </li>
                  ))}
                </ol>
              </Card>
            )}
          </div>

          {/* ── 타깃 오디언스 + 스토리 구조 ───────────────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
            {ar.target_audience && (
              <Card>
                <Label>👥 타깃 오디언스</Label>
                <p style={{ fontSize: 13, lineHeight: 1.6, color: '#A8B6CB', margin: 0 }}>{ar.target_audience}</p>
              </Card>
            )}
            {ar.story_structure && (
              <Card>
                <Label>📐 스토리 구조</Label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                  {ar.story_structure.intro_style && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span style={{ color: '#F59E0B', fontWeight: 600, flexShrink: 0 }}>인트로</span>
                      <span style={{ color: '#A8B6CB' }}>{ar.story_structure.intro_style}</span>
                    </div>
                  )}
                  {ar.story_structure.main_body_format && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span style={{ color: '#10B981', fontWeight: 600, flexShrink: 0 }}>본론</span>
                      <span style={{ color: '#A8B6CB' }}>{ar.story_structure.main_body_format}</span>
                    </div>
                  )}
                  {ar.story_structure.conclusion_style && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span style={{ color: '#5B78F6', fontWeight: 600, flexShrink: 0 }}>결론</span>
                      <span style={{ color: '#A8B6CB' }}>{ar.story_structure.conclusion_style}</span>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>
        </div>
      )
    }

    case 2: return null

    case 3: {
      const voice = data.voice
      const caption = data.caption
      if (!voice && !caption) return null
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {voice?.file_path && (
            <Card>
              <Label>🎙️ 음성 파일</Label>
              <audio controls src={voice.file_path} style={{ width: '100%', borderRadius: 8, marginTop: 4, colorScheme: 'dark' }} />
              {voice.metadata && (
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <Tag color="#10B981">{voice.metadata.segments}개 씬</Tag>
                  {voice.metadata.size_bytes && <Tag color="#8A9BBF">{(voice.metadata.size_bytes / 1024).toFixed(0)} KB</Tag>}
                </div>
              )}
            </Card>
          )}
          {caption?.file_path && (
            <Card>
              <Label>📄 자막 파일 (SRT)</Label>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Tag color="#14B8A6">SRT</Tag>
                  {caption.metadata?.entries > 0 && <Tag color="#8A9BBF">{caption.metadata.entries}개 항목</Tag>}
                </div>
                <a
                  href={caption.file_path}
                  download="captions.srt"
                  style={{ fontSize: 12, fontWeight: 500, color: '#5B78F6', textDecoration: 'none' }}
                >
                  ↓ 다운로드
                </a>
              </div>
            </Card>
          )}
        </div>
      )
    }

    case 4: {
      const scenes = data.scenes || []
      if (!scenes.length) return null
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Label>🎬 스토리보드 ({scenes.length}씬)</Label>
          {scenes.map((s) => {
            const m = s.metadata || s
            return (
              <Card key={s.scene_id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: 'rgba(91,120,246,0.15)', color: '#5B78F6' }}>씬 {s.scene_id}</span>
                  {m.timestamp && <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#8A9BBF' }}>{m.timestamp}</span>}
                  <span style={{ fontSize: 13, fontWeight: 500, color: '#C8D4F0' }}>{m.description}</span>
                </div>
                {m.narration && (
                  <p style={{
                    fontSize: 12, fontStyle: 'italic', lineHeight: 1.6,
                    marginBottom: 10, paddingLeft: 12,
                    borderLeft: '2px solid #5B78F6', color: '#A8B6CB',
                  }}>
                    "{m.narration}"
                  </p>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
                  {m.image_prompt && (
                    <div style={{ borderRadius: 8, padding: '8px 12px', background: 'rgba(139,92,246,0.08)' }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#8B5CF6', marginBottom: 4, margin: '0 0 4px' }}>이미지 프롬프트</p>
                      <p style={{ fontSize: 11, color: '#A8B6CB', margin: 0 }}>{m.image_prompt}</p>
                    </div>
                  )}
                  {m.video_prompt && (
                    <div style={{ borderRadius: 8, padding: '8px 12px', background: 'rgba(20,184,166,0.08)' }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#14B8A6', marginBottom: 4, margin: '0 0 4px' }}>영상 프롬프트</p>
                      <p style={{ fontSize: 11, color: '#A8B6CB', margin: 0 }}>{m.video_prompt}</p>
                    </div>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )
    }

    case 5: {
      const scenes = data.scenes || []
      if (!scenes.length) return null
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Label>🖼️ 씬 이미지 + 영상 ({scenes.length}씬)</Label>
          {scenes.map((s) => (
            <Card key={s.scene_id}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Tag color="#5B78F6">씬 {s.scene_id}</Tag>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                {s.image?.file_path && (
                  <div>
                    <p style={{ fontSize: 11, color: '#8A9BBF', marginBottom: 6, margin: '0 0 6px' }}>이미지</p>
                    <img src={s.image.file_path} alt={`scene ${s.scene_id}`} style={{ width: '100%', borderRadius: 8, objectFit: 'cover', aspectRatio: '16/9', display: 'block' }} />
                    {s.image.metadata?.image_prompt && (
                      <p style={{ fontSize: 11, marginTop: 6, fontStyle: 'italic', color: '#8A9BBF', margin: '6px 0 0' }}>
                        {s.image.metadata.image_prompt.slice(0, 80)}…
                      </p>
                    )}
                  </div>
                )}
                {s.video?.file_path && (
                  <div>
                    <p style={{ fontSize: 11, color: '#8A9BBF', marginBottom: 6, margin: '0 0 6px' }}>영상 클립</p>
                    <video controls src={s.video.file_path} style={{ width: '100%', borderRadius: 8, aspectRatio: '16/9', display: 'block' }} />
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )
    }

    case 6: {
      const fv = data.final_video || {}
      const ym = data.youtube_meta || {}
      if (!fv.file_path && !ym.title) return null
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {fv.file_path && (
            <Card>
              <Label>🎬 최종 영상</Label>
              <video controls src={fv.file_path} style={{ width: '100%', borderRadius: 8, marginTop: 4, display: 'block' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
                {fv.metadata?.size_bytes && <Tag color="#8A9BBF">{(fv.metadata.size_bytes / 1048576).toFixed(1)} MB</Tag>}
                {fv.metadata?.scenes && <Tag color="#8A9BBF">{fv.metadata.scenes}씬</Tag>}
                {fv.metadata?.burn_subtitles && <Tag color="#F59E0B">자막 하드코딩</Tag>}
                <a href={fv.file_path} download="final_video.mp4" style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 500, color: '#5B78F6', textDecoration: 'none' }}>↓ MP4 다운로드</a>
              </div>
            </Card>
          )}
          {ym.title && (
            <Card>
              <Label>📋 AI 생성 YouTube 메타데이터 (Step 8에서 편집 가능)</Label>
              <p style={{ fontSize: 14, fontWeight: 600, color: '#E8EEFF', margin: '0 0 8px' }}>{ym.title}</p>
              {ym.description && <p style={{ fontSize: 13, lineHeight: 1.6, color: '#A8B6CB', margin: '0 0 12px' }}>{ym.description}</p>}
              {ym.tags?.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {ym.tags.map((t, i) => <Tag key={i} color="#5B78F6">#{t}</Tag>)}
                </div>
              )}
            </Card>
          )}
        </div>
      )
    }

    case 7: {
      if (!data.file_path) return null
      const tm = data.metadata || {}
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card>
            <Label>🎨 생성된 썸네일</Label>
            <div style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', marginTop: 4 }}>
              <img src={data.file_path} alt="thumbnail" style={{ width: '100%', objectFit: 'cover', aspectRatio: '16/9', display: 'block' }} />
              {tm.overlay_text && (
                <div style={{
                  position: 'absolute', bottom: 12, left: 12,
                  color: 'white', fontSize: 13, fontWeight: 700,
                  padding: '6px 12px', borderRadius: 8,
                  background: 'rgba(0,0,0,0.75)',
                }}>
                  {tm.overlay_text}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
              {tm.size_bytes && <Tag color="#8A9BBF">{(tm.size_bytes / 1024).toFixed(0)} KB</Tag>}
              <a href={data.file_path} download="thumbnail.png" style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 500, color: '#5B78F6', textDecoration: 'none' }}>↓ PNG 다운로드</a>
            </div>
          </Card>
          {tm.style_notes && (
            <Card>
              <Label>디자인 전략</Label>
              <p style={{ fontSize: 13, lineHeight: 1.6, color: '#A8B6CB', margin: 0 }}>{tm.style_notes}</p>
            </Card>
          )}
          {tm.image_prompt && (
            <Card>
              <Label>이미지 프롬프트</Label>
              <p style={{ fontSize: 12, fontFamily: 'monospace', lineHeight: 1.6, color: '#8A9BBF', margin: 0 }}>{tm.image_prompt}</p>
            </Card>
          )}
        </div>
      )
    }

    case 8: {
      const vid = data.youtube_video_id
      const ym = data.youtube_meta || {}
      // Always show something — video or OAuth setup guide
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {vid ? (
            <Card>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
                {ym.thumbnail_url && (
                  <img src={ym.thumbnail_url} alt="thumbnail"
                    style={{ width: 128, borderRadius: 8, aspectRatio: '16/9', objectFit: 'cover', flexShrink: 0 }} />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#10B981' }}>YouTube 업로드 완료!</span>
                  </div>
                  {ym.title && <p style={{ fontSize: 13, fontWeight: 500, color: '#E8EEFF', margin: '0 0 14px', lineHeight: 1.4 }}>{ym.title}</p>}
                  <a href={`https://www.youtube.com/watch?v=${vid}`} target="_blank" rel="noopener noreferrer"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, padding: '7px 16px', borderRadius: 8, background: '#EF4444', color: 'white', textDecoration: 'none' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M23.5 6.19a3.02 3.02 0 0 0-2.12-2.14C19.54 3.5 12 3.5 12 3.5s-7.54 0-9.38.55A3.02 3.02 0 0 0 .5 6.19C0 8.04 0 12 0 12s0 3.96.5 5.81a3.02 3.02 0 0 0 2.12 2.14C4.46 20.5 12 20.5 12 20.5s7.54 0 9.38-.55a3.02 3.02 0 0 0 2.12-2.14C24 15.96 24 12 24 12s0-3.96-.5-5.81zM9.75 15.52V8.48L15.5 12l-5.75 3.52z"/>
                    </svg>
                    YouTube에서 보기
                  </a>
                </div>
              </div>
            </Card>
          ) : (
            <Card style={{ borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.06)' }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ fontSize: 18, flexShrink: 0 }}>🔑</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#F59E0B', marginBottom: 6 }}>YouTube OAuth 설정 필요</div>
                  <div style={{ fontSize: 12, color: '#D4A754', lineHeight: 1.6 }}>
                    영상은 Step 6에서 확인하거나 MP4로 다운로드할 수 있습니다.<br/>
                    YouTube 업로드를 원하시면 <code style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 5px', borderRadius: 4 }}>GET /auth/youtube</code> 에서 OAuth 인증을 완료해주세요.
                  </div>
                </div>
              </div>
            </Card>
          )}
          {ym.title && (
            <Card>
              <Label>📋 YouTube 메타데이터</Label>
              <p style={{ fontSize: 14, fontWeight: 600, color: '#E8EEFF', margin: '0 0 6px' }}>{ym.title}</p>
              {ym.description && <p style={{ fontSize: 12, color: '#A8B6CB', lineHeight: 1.6, margin: '0 0 10px' }}>{ym.description}</p>}
              {ym.tags?.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {ym.tags.map((t, i) => <Tag key={i} color="#5B78F6">#{t}</Tag>)}
                </div>
              )}
            </Card>
          )}
        </div>
      )
    }

    default: return null
  }
}

// ── InputField helper ──────────────────────────────────────────────────────────
function InputField({ field, value, onChange }) {
  const [focused, setFocused] = useState(false)
  const style = { ...(focused ? inputFocusStyle : inputStyle) }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 7 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#C8D4F0' }}>{field.label}</span>
        {field.hint && <span style={{ fontSize: 11, color: '#8A9BBF' }}>— {field.hint}</span>}
      </div>
      {field.type === 'textarea' || field.type === 'textarea-urls' ? (
        <textarea value={value || ''} onChange={e => onChange(e.target.value)} placeholder={field.placeholder}
          rows={3} style={{ ...style, resize: 'vertical', lineHeight: 1.6 }}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        />
      ) : field.type === 'toggle' ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            onClick={() => onChange(!value)}
            style={{ width: 44, height: 24, borderRadius: 12, background: value ? '#5B78F6' : '#253550', border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s', flexShrink: 0 }}
          >
            <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'white', position: 'absolute', top: 3, left: value ? 23 : 3, transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
          </button>
          {field.hint && <span style={{ fontSize: 12, color: '#8A9BBF' }}>{field.hint}</span>}
        </div>
      ) : (
        <input type="text" value={value || ''} onChange={e => onChange(e.target.value)} placeholder={field.placeholder}
          style={style} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        />
      )}
    </div>
  )
}

// ── OptionField helper ─────────────────────────────────────────────────────────
function OptionField({ opt, value, onChange }) {
  if (opt.type === 'toggle') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#C8D4F0' }}>{opt.label}</span>
          {opt.hint && <p style={{ margin: '2px 0 0', fontSize: 11, color: '#8A9BBF' }}>{opt.hint}</p>}
        </div>
        <button
          onClick={() => onChange(!value)}
          style={{ width: 44, height: 24, borderRadius: 12, background: value ? '#10B981' : '#253550', border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s', flexShrink: 0 }}
        >
          <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'white', position: 'absolute', top: 3, left: value ? 23 : 3, transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }} />
        </button>
      </div>
    )
  }

  if (opt.type === 'select') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#C8D4F0' }}>{opt.label}</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {opt.options.map((o, i) => (
            <button key={o} onClick={() => onChange(o)}
              style={{ padding: '4px 10px', borderRadius: 7, fontSize: 11, fontWeight: 500, border: `1px solid ${value === o ? '#5B78F6' : '#253550'}`, background: value === o ? 'rgba(91,120,246,0.15)' : 'transparent', color: value === o ? '#5B78F6' : '#8A9BBF', cursor: 'pointer', transition: 'all 0.15s', whiteSpace: 'nowrap' }}
            >
              {opt.optionLabels?.[i] || o}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return null
}

// ── Default value resolver ─────────────────────────────────────────────────────
// Maps project-level settings to per-step field/option keys
const PROJECT_DEFAULTS_MAP = {
  // stepNum -> { fields: {key: projectDefaultsKey}, options: {key: projectDefaultsKey} }
  1: { fields: { keyword: 'keyword' }, options: {} },
  2: { fields: {}, options: { target_duration: 'target_duration', tone: 'tone' } },
  4: { fields: {}, options: {} },
  5: { fields: {}, options: { genre: 'genre' } },
  8: { fields: {}, options: { privacy: 'privacy' } },
}

function buildInitialValues(stepNum, meta, projectDefaults = {}) {
  const map = PROJECT_DEFAULTS_MAP[stepNum] || { fields: {}, options: {} }

  const fields = {}
  ;(meta.manualInputs || []).forEach(f => {
    const pd = map.fields[f.key]
    if (pd && projectDefaults[pd]) fields[f.key] = projectDefaults[pd]
  })

  const options = {}
  ;(meta.autoOptions || []).forEach(o => {
    const pd = map.options[o.key]
    const fromProject = pd && projectDefaults[pd]
    options[o.key] = fromProject
      ? fromProject
      : o.type === 'toggle' ? (o.defaultChecked ?? false) : (o.default ?? '')
  })

  return { fields, options }
}

// ── Main StepCard ──────────────────────────────────────────────────────────────
export default function StepCard({ step, projectId, status, onStatusChange, projectDefaults = {} }) {
  const meta = STEP_META[step.num] || { desc: '', manualInputs: [], autoOptions: [] }
  const isDone = status === 'done'
  const isRunning = status === 'running'
  const isAwaitingReview = status === 'awaiting_review'
  const isError = status === 'error'

  const { fields: initFields, options: initOptions } = buildInitialValues(step.num, meta, projectDefaults)
  const [fields, setFields] = useState(initFields)
  const [options, setOptions] = useState(initOptions)
  const [optionsOpen, setOptionsOpen] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [dataLoading, setDataLoading] = useState(false)
  const [scriptDraft, setScriptDraft] = useState('')
  const [approving, setApproving] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [cancelling, setCancelling] = useState(false)
  const pollingRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null }
  }, [])

  const fetchData = useCallback(async () => {
    setDataLoading(true)
    try { const res = await getStepData(projectId, step.num); setData(res.data) }
    catch (e) { /* ignore */ }
    finally { setDataLoading(false) }
  }, [projectId, step.num])

  const startPolling = useCallback(() => {
    stopPolling()
    pollingRef.current = setInterval(async () => {
      try {
        const res = await getStepStatus(projectId, step.num)
        const { status: s, message, progress: pct } = res.data
        if (pct != null) setProgress(pct)
        if (message) setProgressMsg(message)
        if (s !== 'running') {
          onStatusChange(step.num, s)
          stopPolling()
          if (s === 'done' || s === 'awaiting_review' || s === 'error') fetchData()
        }
      } catch (e) { /* ignore poll errors */ }
    }, 2000)
  }, [projectId, step.num, onStatusChange, stopPolling, fetchData])

  // Re-apply project defaults when they load (async from localStorage)
  useEffect(() => {
    if (!Object.keys(projectDefaults).length) return
    const { fields: f, options: o } = buildInitialValues(step.num, meta, projectDefaults)
    setFields(prev => ({ ...f, ...prev }))   // don't overwrite already-edited fields
    setOptions(prev => ({ ...o, ...prev }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectDefaults])

  useEffect(() => {
    if (status === 'running') startPolling()
    else stopPolling()
    return () => stopPolling()
  }, [status, startPolling, stopPolling])

  useEffect(() => {
    if (status === 'done' || status === 'awaiting_review') fetchData()
  }, [status, fetchData])

  useEffect(() => {
    if (status === 'awaiting_review' && data?.final_script) setScriptDraft(data.final_script)
  }, [status, data])

  // Pre-fill step 8 from step 6 YouTube meta
  useEffect(() => {
    if (step.num === 8 && status !== 'done') {
      getStepData(projectId, 6).then(res => {
        const m = res.data?.youtube_meta || {}
        if (m.title) setFields(prev => ({ ...prev, title: m.title, description: m.description || '', tags: (m.tags || []).join(', ') }))
      }).catch(() => {})
    }
  }, [step.num, projectId, status])

  const handleRun = async () => {
    setError(null)
    setProgress(0)
    setProgressMsg('시작 중...')
    try {
      const payload = { ...fields, ...options }
      // Step 1: convert newline-separated youtube_urls textarea → array
      if (step.num === 1 && typeof payload.youtube_urls === 'string') {
        payload.youtube_urls = payload.youtube_urls
          .split('\n')
          .map(u => u.trim())
          .filter(Boolean)
      }
      if (step.num === 8) {
        payload.title = fields.title
        payload.description = fields.description
        payload.tags = fields.tags?.split(',').map(t => t.trim()).filter(Boolean)
        payload.privacy = options.privacy || 'public'
      }
      await runStep(projectId, step.num, payload)
      onStatusChange(step.num, 'running')
      startPolling()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || '실행 실패')
    }
  }

  const handleCancel = async () => {
    setCancelling(true)
    try {
      await cancelStep(projectId, step.num)
      stopPolling()
      setProgress(0)
      setProgressMsg('')
      onStatusChange(step.num, 'pending')
    } catch (e) {
      setError(e.response?.data?.detail || '취소 실패')
    } finally { setCancelling(false) }
  }

  const handleApproveScript = async () => {
    setApproving(true)
    try {
      await approveScript(projectId, scriptDraft)
      onStatusChange(step.num, 'done')
      fetchData()
    } catch (e) {
      setError(e.response?.data?.detail || '승인 실패')
    } finally { setApproving(false) }
  }

  const setField = (key, val) => setFields(prev => ({ ...prev, [key]: val }))
  const setOption = (key, val) => setOptions(prev => ({ ...prev, [key]: val }))

  const st = STATUS[status] || STATUS.pending

  return (
    <div style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: 'linear-gradient(135deg, rgba(91,120,246,0.2), rgba(139,92,246,0.2))', border: '1px solid rgba(91,120,246,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
            {step.icon}
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#E8EEFF', letterSpacing: '-0.3px' }}>
              Step {step.num}: {step.name}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#8A9BBF', lineHeight: 1.5, maxWidth: 480 }}>
              {meta.desc}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, paddingTop: 2 }}>
          <span style={{ fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 8, background: st.bg, color: st.color, whiteSpace: 'nowrap' }}>
            {st.label}
          </span>
        </div>
      </div>

      {/* ── Project defaults banner ── */}
      {!isDone && !isRunning && !isAwaitingReview && Object.keys(projectDefaults).length > 0 && (() => {
        const map = PROJECT_DEFAULTS_MAP[step.num] || { fields: {}, options: {} }
        const active = []
        Object.entries({ ...map.fields, ...map.options }).forEach(([fieldKey, pdKey]) => {
          if (projectDefaults[pdKey]) {
            const allMeta = [...(meta.manualInputs || []), ...(meta.autoOptions || [])]
            const m = allMeta.find(x => x.key === fieldKey)
            const label = m?.label || fieldKey
            const val = projectDefaults[pdKey]
            // Find human-readable label for select options
            const optMeta = (meta.autoOptions || []).find(o => o.key === fieldKey)
            let displayVal = val
            if (optMeta?.options) {
              const idx = optMeta.options.indexOf(val)
              displayVal = (idx !== -1 && optMeta.optionLabels?.[idx]) ? optMeta.optionLabels[idx] : val
            }
            active.push({ label, value: displayVal })
          }
        })
        if (!active.length) return null
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: 12, background: 'rgba(91,120,246,0.07)', border: '1px solid rgba(91,120,246,0.18)' }}>
            <span style={{ fontSize: 13, flexShrink: 0 }}>✨</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#5B78F6', marginRight: 8 }}>프로젝트 설정 적용됨</span>
              <span style={{ fontSize: 11, color: '#8A9BBF' }}>
                {active.map(a => `${a.label}: ${a.value}`).join(' · ')}
              </span>
            </div>
          </div>
        )
      })()}

      {/* ── Error ── */}
      {isError && error && (
        <Card style={{ borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#EF4444', marginBottom: 4 }}>오류 발생</div>
              <div style={{ fontSize: 12, color: '#F87171', lineHeight: 1.5 }}>{error}</div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Progress (running state) ── */}
      {isRunning && (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: '#F59E0B', fontWeight: 500 }}>
                {progressMsg || '처리 중...'}
              </span>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#F59E0B', fontVariantNumeric: 'tabular-nums' }}>
                {progress}%
              </span>
            </div>
            <div style={{ height: 8, background: '#172336', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
              <div style={{
                height: '100%',
                background: 'linear-gradient(90deg, #F59E0B, #F97316)',
                borderRadius: 4,
                width: `${progress}%`,
                transition: 'width 0.6s ease',
                boxShadow: progress > 0 ? '0 0 8px rgba(245,158,11,0.5)' : 'none',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
              <div style={{ display: 'flex', gap: 4, flex: 1 }}>
                {[20, 40, 60, 80, 100].map(milestone => (
                  <div key={milestone} style={{ flex: 1, height: 3, borderRadius: 2, background: progress >= milestone ? '#F59E0B' : '#253550', transition: 'background 0.4s' }} />
                ))}
              </div>
              <button
                onClick={handleCancel}
                disabled={cancelling}
                style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'rgba(239,68,68,0.12)', color: '#F87171', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '5px 12px', fontSize: 12, fontWeight: 600, cursor: cancelling ? 'not-allowed' : 'pointer', flexShrink: 0 }}
                onMouseEnter={e => { if (!cancelling) e.currentTarget.style.background='rgba(239,68,68,0.2)' }}
                onMouseLeave={e => e.currentTarget.style.background='rgba(239,68,68,0.12)'}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
                {cancelling ? '취소 중...' : '취소'}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* ── Awaiting review banner (step 2) ── */}
      {isAwaitingReview && (
        <Card style={{ borderColor: 'rgba(167,139,250,0.3)', background: 'rgba(167,139,250,0.08)' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 16 }}>📋</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#A78BFA' }}>대본 검토가 필요합니다</div>
              <div style={{ fontSize: 12, color: '#C4B5FD', marginTop: 2 }}>아래 대본을 확인하고 수정한 후 승인하면 다음 단계로 진행됩니다.</div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Inputs (not running, not done, not awaiting_review) ── */}
      {!isRunning && !isDone && !isAwaitingReview && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Manual inputs */}
          {meta.manualInputs?.length > 0 && (
            <Card>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#5B78F6' }} />
                <span style={{ fontSize: 11, fontWeight: 700, color: '#5B78F6', textTransform: 'uppercase', letterSpacing: '0.7px' }}>수동 입력</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {meta.manualInputs.map(f => (
                  <InputField key={f.key} field={f} value={fields[f.key]} onChange={v => setField(f.key, v)} />
                ))}
              </div>
            </Card>
          )}

          {/* Auto options (collapsible) */}
          {meta.autoOptions?.length > 0 && (
            <div style={{ border: '1px solid #253550', borderRadius: 14, overflow: 'hidden' }}>
              <button
                onClick={() => setOptionsOpen(o => !o)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 18px', background: '#111A2E', border: 'none', cursor: 'pointer', textAlign: 'left' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981' }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#10B981', textTransform: 'uppercase', letterSpacing: '0.7px' }}>자동 처리 옵션</span>
                  <span style={{ fontSize: 11, color: '#8A9BBF', marginLeft: 4 }}>— 기본값으로도 바로 실행 가능</span>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#8A9BBF" strokeWidth="2" style={{ transform: optionsOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </button>
              {optionsOpen && (
                <div style={{ padding: '14px 18px 16px', background: '#0E1723', borderTop: '1px solid #253550', display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {meta.autoOptions.map(opt => (
                    <OptionField key={opt.key} opt={opt} value={options[opt.key]} onChange={v => setOption(opt.key, v)} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Step 2: Script editor (awaiting_review or done) ── */}
      {step.num === 2 && (isAwaitingReview || isDone) && data?.final_script && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {data.planning_doc && <PlanningDocView doc={typeof data.planning_doc === 'string' ? JSON.parse(data.planning_doc) : data.planning_doc} />}
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <Label>최종 대본 (직접 수정 가능)</Label>
              {isAwaitingReview && (
                <span style={{ fontSize: 11, color: '#A78BFA', fontWeight: 500 }}>
                  {scriptDraft.length.toLocaleString()}자
                </span>
              )}
            </div>
            <textarea
              value={isAwaitingReview ? scriptDraft : (data.final_script || '')}
              onChange={e => isAwaitingReview && setScriptDraft(e.target.value)}
              readOnly={!isAwaitingReview}
              rows={18}
              style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.7, fontFamily: 'monospace', fontSize: 12, opacity: isAwaitingReview ? 1 : 0.7 }}
            />
            {isAwaitingReview && (
              <button
                onClick={handleApproveScript}
                disabled={approving || !scriptDraft.trim()}
                style={{ marginTop: 12, width: '100%', padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: approving ? '#253550' : 'linear-gradient(135deg, #5B78F6, #8B5CF6)', color: approving ? '#8A9BBF' : 'white', border: 'none', cursor: approving ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
              >
                {approving ? '승인 중...' : '✓ 대본 승인 후 다음 단계로'}
              </button>
            )}
          </Card>
        </div>
      )}

      {/* ── Step 8: YouTube metadata editor ── */}
      {step.num === 8 && !isDone && !isRunning && (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#EF4444' }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: '#EF4444', textTransform: 'uppercase', letterSpacing: '0.7px' }}>YouTube 메타데이터</span>
            <span style={{ fontSize: 11, color: '#8A9BBF', marginLeft: 2 }}>— AI 생성값 자동 로드됨</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { key: 'title', label: '제목', type: 'text', placeholder: 'AI가 자동으로 채워줍니다' },
              { key: 'description', label: '설명', type: 'textarea', placeholder: 'AI가 자동으로 채워줍니다', rows: 5 },
              { key: 'tags', label: '태그 (쉼표로 구분)', type: 'text', placeholder: 'ETF, 투자, 주식, 초보자' },
            ].map(f => (
              <div key={f.key}>
                <Label>{f.label}</Label>
                {f.type === 'textarea' ? (
                  <textarea value={fields[f.key] || ''} onChange={e => setField(f.key, e.target.value)} placeholder={f.placeholder} rows={f.rows || 3}
                    style={{ ...inputStyle, resize: 'vertical' }}
                    onFocus={e => e.target.style.borderColor='#5B78F6'}
                    onBlur={e => e.target.style.borderColor='#253550'}
                  />
                ) : (
                  <input value={fields[f.key] || ''} onChange={e => setField(f.key, e.target.value)} placeholder={f.placeholder}
                    style={inputStyle}
                    onFocus={e => e.target.style.borderColor='#5B78F6'}
                    onBlur={e => e.target.style.borderColor='#253550'}
                  />
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Run button (not running, not done, not awaiting_review) ── */}
      {!isRunning && !isDone && !isAwaitingReview && (
        <button
          onClick={handleRun}
          style={{ width: '100%', padding: '14px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: 'linear-gradient(135deg, #5B78F6 0%, #7B68EE 100%)', color: 'white', border: 'none', cursor: 'pointer', transition: 'all 0.15s', letterSpacing: '0.3px' }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '0.9'; e.currentTarget.style.transform = 'translateY(-1px)' }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'none' }}
        >
          Step {step.num} 실행 →
        </button>
      )}

      {/* ── Re-run button (done state) ── */}
      {isDone && step.num !== 2 && (
        <button
          onClick={handleRun}
          style={{ width: '100%', padding: '10px', borderRadius: 10, fontSize: 13, fontWeight: 600, background: 'transparent', color: '#8A9BBF', border: '1px solid #253550', cursor: 'pointer', transition: 'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background='#111A2E'; e.currentTarget.style.color='#E8EEFF' }}
          onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='#8A9BBF' }}
        >
          ↺ 다시 실행
        </button>
      )}

      {/* ── Output ── */}
      {(isDone || isAwaitingReview) && dataLoading && (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#8A9BBF', fontSize: 13 }}>
            <div style={{ width: 16, height: 16, border: '2px solid #253550', borderTopColor: '#5B78F6', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            결과물 로딩 중...
          </div>
        </Card>
      )}
      {(isDone || isAwaitingReview) && data && step.num !== 2 && (
        <StepOutput step={step.num} data={data} />
      )}
      {isDone && data && step.num === 2 && null /* handled above */}
    </div>
  )
}

// ── PlanningDocView ────────────────────────────────────────────────────────────
function PlanningDocView({ doc }) {
  if (!doc) return null
  const concept = doc.story_concept || {}
  const ctr = doc.ctr_design || {}
  const hook = doc.hook_intro_strategy || {}
  const outline = doc.content_outline || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, fontSize: 13 }}>
      {(concept.main_theme || concept.narrative_angle) && (
        <div>
          <Label>스토리 컨셉</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {concept.main_theme && (
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: '#5B78F6', width: '4rem', flexShrink: 0, fontWeight: 500 }}>핵심 주제</span>
                <span style={{ color: '#A8B6CB' }}>{concept.main_theme}</span>
              </div>
            )}
            {concept.narrative_angle && (
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: '#5B78F6', width: '4rem', flexShrink: 0, fontWeight: 500 }}>앵글</span>
                <span style={{ color: '#A8B6CB' }}>{concept.narrative_angle}</span>
              </div>
            )}
            {concept.unique_value_proposition && (
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: '#5B78F6', width: '4rem', flexShrink: 0, fontWeight: 500 }}>UVP</span>
                <span style={{ color: '#A8B6CB' }}>{concept.unique_value_proposition}</span>
              </div>
            )}
          </div>
        </div>
      )}
      {ctr.title_candidates?.length > 0 && (
        <div>
          <Label>제목 후보</Label>
          <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
            {ctr.title_candidates.map((t, i) => (
              <li key={i} style={{ display: 'flex', gap: 8 }}>
                <span style={{ color: '#F59E0B', fontWeight: 700, width: 16, flexShrink: 0 }}>{i + 1}.</span>
                <span style={{ color: '#C8D4F0' }}>{t}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {hook.opening_hook && (
        <div>
          <Label>훅 &amp; 인트로</Label>
          <div style={{ borderRadius: 8, padding: '8px 12px', marginBottom: 8, background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.18)' }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#F59E0B', margin: '0 0 4px' }}>오프닝 훅</p>
            <p style={{ color: '#FDE68A', margin: 0 }}>"{hook.opening_hook}"</p>
          </div>
        </div>
      )}
      {outline.length > 0 && (
        <div>
          <Label>콘텐츠 구성 ({doc.estimated_duration || ''})</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {outline.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, borderRadius: 8, padding: '8px 12px', background: '#172336' }}>
                <span style={{ fontSize: 11, width: 56, flexShrink: 0, paddingTop: 2, fontFamily: 'monospace', color: '#8A9BBF' }}>{s.timecode}</span>
                <div>
                  <p style={{ color: '#E8EEFF', fontWeight: 600, fontSize: 12, margin: '0 0 4px' }}>{s.section_name}</p>
                  {s.key_points?.map((pt, j) => (
                    <p key={j} style={{ fontSize: 11, color: '#8A9BBF', margin: '0 0 2px' }}>· {pt}</p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
