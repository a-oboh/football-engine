CREATE DATABASE football_analytics;

CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,

    name VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
)