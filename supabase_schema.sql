-- Выполни это в SQL Editor Supabase

CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    joined_at TIMESTAMP DEFAULT NOW(),
    sleep_time TIME DEFAULT '23:00',
    wake_time TIME DEFAULT '07:00',
    water_reminder BOOLEAN DEFAULT TRUE
);

CREATE TABLE challenges (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    exercise_type TEXT NOT NULL,
    daily_target INTEGER NOT NULL,
    total_target INTEGER,
    days INTEGER,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    total_done INTEGER DEFAULT 0,
    start_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE daily_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    challenge_id INTEGER REFERENCES challenges(id),
    amount INTEGER NOT NULL,
    log_date DATE DEFAULT CURRENT_DATE,
    log_time TIMESTAMP DEFAULT NOW()
);

CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    goal_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    progress INTEGER DEFAULT 0,
    is_completed BOOLEAN DEFAULT FALSE,
    month_year TEXT NOT NULL
);

CREATE TABLE achievements (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    achievement_name TEXT NOT NULL,
    achievement_type TEXT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE daily_checks (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    check_date DATE DEFAULT CURRENT_DATE,
    sleep_check BOOLEAN DEFAULT FALSE,
    water_check BOOLEAN DEFAULT FALSE
);