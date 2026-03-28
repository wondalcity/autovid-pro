-- AutoVidPro: step_logs 테이블 및 관련 마이그레이션
-- Run this in Supabase SQL Editor or via CLI

CREATE TABLE IF NOT EXISTS public.step_logs (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid        NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  step_num     integer     NOT NULL,
  status       text        NOT NULL CHECK (status IN ('pending','running','awaiting_review','done','error')),
  message      text,
  progress     integer     DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  started_at   timestamptz,
  finished_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, step_num)
);

CREATE INDEX IF NOT EXISTS step_logs_project_step_idx
  ON public.step_logs (project_id, step_num);

-- youtube_meta UNIQUE 제약 (upsert 정상 동작용)
ALTER TABLE public.youtube_meta
  ADD CONSTRAINT IF NOT EXISTS youtube_meta_project_id_key UNIQUE (project_id);

-- projects에 youtube_video_id 컬럼 추가
ALTER TABLE public.projects
  ADD COLUMN IF NOT EXISTS youtube_video_id text;
