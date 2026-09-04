CREATE TABLE IF NOT EXISTS tenants (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Only the sha256 of a key is stored, never the key itself.
CREATE TABLE IF NOT EXISTS api_keys (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT 'default',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_hash_idx ON api_keys (key_hash);

-- id is a TEXT because it is a random string, not a counter (it goes in a public URL).
CREATE TABLE IF NOT EXISTS widgets (
    id              TEXT PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    fields          JSONB NOT NULL DEFAULT '[]'::jsonb,
    button_text     TEXT NOT NULL DEFAULT 'Submit',
    options         JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_version  INTEGER NOT NULL DEFAULT 1,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS widgets_tenant_idx ON widgets (tenant_id, created_at DESC);

-- tenant_id is copied onto the row so dashboard queries don't need a join.
-- data is JSONB because the owner can change the field list later and old
-- submissions still have to keep exactly what was sent.
CREATE TABLE IF NOT EXISTS submissions (
    id               BIGSERIAL PRIMARY KEY,
    widget_id        TEXT NOT NULL REFERENCES widgets(id) ON DELETE CASCADE,
    tenant_id        BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    data             JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip               TEXT,
    user_agent       TEXT,
    referer          TEXT,
    country          TEXT,
    country_code     TEXT,
    city             TEXT,
    geo_provider     TEXT,
    geo_status       TEXT NOT NULL DEFAULT 'unavailable',
    is_spam          BOOLEAN NOT NULL DEFAULT FALSE,
    spam_reason      TEXT,
    idempotency_key  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS submissions_widget_idx ON submissions (widget_id, created_at DESC);
CREATE INDEX IF NOT EXISTS submissions_tenant_idx ON submissions (tenant_id, created_at DESC);

-- Partial index: the key may be NULL when the caller doesn't send one, but two
-- rows can never share the same key for the same widget.
CREATE UNIQUE INDEX IF NOT EXISTS submissions_idempotency_idx
    ON submissions (widget_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS notification_jobs (
    id               BIGSERIAL PRIMARY KEY,
    submission_id    BIGINT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    status           TEXT NOT NULL DEFAULT 'pending',
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The worker only ever asks "which jobs are due?", so this is the index it needs.
CREATE INDEX IF NOT EXISTS notification_jobs_due_idx
    ON notification_jobs (status, next_attempt_at);

-- One submission, one notification.
CREATE UNIQUE INDEX IF NOT EXISTS notification_jobs_submission_idx
    ON notification_jobs (submission_id);
