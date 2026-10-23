-- Migration 001: baseline schema for the Store Sales Forecasting app
-- Replaces the MongoDB "forecast history" collection written by dashboard.py

BEGIN;

CREATE TABLE IF NOT EXISTS forecast_history (
    id           BIGSERIAL        PRIMARY KEY,
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT now(),
    store_nbr    INTEGER          NOT NULL,
    family       TEXT             NOT NULL,
    horizon      INTEGER          NOT NULL CHECK (horizon > 0),
    onpromotion  INTEGER[]        NOT NULL,
    is_holiday   INTEGER[]        NOT NULL,
    predictions  JSONB            NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_forecast_history_created_at
    ON forecast_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_history_store_family
    ON forecast_history (store_nbr, family);

-- Tracks files uploaded through the app and stored in object storage (Blob)
CREATE TABLE IF NOT EXISTS uploaded_files (
    id             BIGSERIAL    PRIMARY KEY,
    uploaded_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    original_name  TEXT         NOT NULL,
    blob_name      TEXT         NOT NULL UNIQUE,
    container      TEXT         NOT NULL,
    size_bytes     BIGINT       NOT NULL CHECK (size_bytes >= 0)
);

COMMIT;
