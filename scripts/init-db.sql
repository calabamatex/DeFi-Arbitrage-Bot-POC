-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create initial database schema
-- This will be replaced by Alembic migrations later

-- Set timezone
SET timezone = 'UTC';

-- Create basic tables (minimal for initialization)
-- Full schema will be managed by Alembic

-- Health check table
CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO health_check (last_check) VALUES (NOW());

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE arbitrage_bot TO postgres;
