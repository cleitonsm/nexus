CREATE TABLE IF NOT EXISTS secret_settings (
    key_name VARCHAR(128) PRIMARY KEY,
    encrypted_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
