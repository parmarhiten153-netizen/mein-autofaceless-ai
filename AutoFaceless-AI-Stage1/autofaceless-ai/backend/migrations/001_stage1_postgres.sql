-- Initial PostgreSQL schema reference for Stage 1.
-- The app currently bootstraps tables with SQLAlchemy create_all; adopt Alembic
-- migrations before applying future production schema changes.
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(320) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
  daily_quota INTEGER NOT NULL DEFAULT 2,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS daily_usage (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  local_date DATE NOT NULL,
  reserved INTEGER NOT NULL DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_daily_usage_user_date UNIQUE(user_id, local_date)
);
CREATE TABLE IF NOT EXISTS video_jobs (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key VARCHAR(128) NOT NULL,
  title VARCHAR(200) NOT NULL DEFAULT 'Untitled video',
  niche VARCHAR(100) NOT NULL DEFAULT 'General',
  language VARCHAR(30) NOT NULL DEFAULT 'Hindi',
  format VARCHAR(20) NOT NULL DEFAULT 'shorts',
  target_duration_seconds INTEGER NOT NULL DEFAULT 60,
  tone VARCHAR(40) NOT NULL DEFAULT 'educational',
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  quota_date DATE NOT NULL,
  quota_reserved BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_job_user_idempotency UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_video_jobs_user_created ON video_jobs(user_id, created_at);
CREATE TABLE IF NOT EXISTS quota_audit (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id INTEGER NULL REFERENCES video_jobs(id) ON DELETE SET NULL,
  local_date DATE NOT NULL,
  action VARCHAR(40) NOT NULL,
  details TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
