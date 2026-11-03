-- Database schema for the TikTok Spending Tracker
-- Tracker: three linked tables, where each purchase belongs to one respondent and one category.
-- Research: two linked tables holding the published DBS survey results.

DROP TABLE IF EXISTS survey_answers;
DROP TABLE IF EXISTS survey_questions;
DROP TABLE IF EXISTS purchases;
DROP TABLE IF EXISTS respondents;
DROP TABLE IF EXISTS categories;

-- Product categories (stored once, referenced by purchases)
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

-- The person who made the purchase (no names or emails are stored)
CREATE TABLE respondents (
    respondent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    age_group     TEXT NOT NULL CHECK (age_group IN ('Under 16', '16-18', '19-21', '22-24', '25+')),
    gender        TEXT NOT NULL,
    hours_per_day REAL NOT NULL CHECK (hours_per_day BETWEEN 0 AND 24)
);

-- One purchase that was influenced by TikTok
CREATE TABLE purchases (
    purchase_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    respondent_id     INTEGER NOT NULL REFERENCES respondents(respondent_id) ON DELETE CASCADE,
    category_id       INTEGER NOT NULL REFERENCES categories(category_id),
    product           TEXT    NOT NULL,
    amount_eur        REAL    NOT NULL CHECK (amount_eur >= 0),
    influence         TEXT    NOT NULL,                                    -- how TikTok influenced it
    would_have_bought INTEGER NOT NULL CHECK (would_have_bought IN (0, 1)), -- 1 = yes, 0 = no
    regret            INTEGER NOT NULL CHECK (regret BETWEEN 1 AND 5),     -- 1 = none, 5 = a lot
    purchase_date     TEXT    NOT NULL                                     -- YYYY-MM-DD
);

-- One question from the published DBS survey
CREATE TABLE survey_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_no TEXT NOT NULL,     -- the number used in the source, e.g. '21'
    question    TEXT NOT NULL UNIQUE,
    responses   INTEGER,           -- how many people answered (blank if not given)
    note        TEXT
);

-- One answer option for a question, with its published result
CREATE TABLE survey_answers (
    answer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES survey_questions(question_id) ON DELETE CASCADE,
    option      TEXT    NOT NULL,
    count       INTEGER,           -- number of people (blank if only a % was given)
    percent     REAL    NOT NULL CHECK (percent BETWEEN 0 AND 100)
);
