"""Builds tiktok_spending.db from schema.sql.

    python init_db.py            research results only, the tracker starts empty
    python init_db.py --sample   also adds 150 made-up demo entries (for testing only)

Running it again wipes the database and reloads everything.
"""
import csv
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tiktok_spending.db"
RESEARCH_CSV = BASE_DIR / "data" / "research_results.csv"
SAMPLE_CSV = BASE_DIR / "data" / "sample_responses.csv"

CATEGORIES = [
    "Beauty & Skincare",
    "Clothing & Fashion",
    "Food & Drink",
    "Tech & Gadgets",
    "Home & Lifestyle",
    "Books",
    "Fitness",
    "Wellness",
    "Other",
]


def load_research(conn, csv_path):
    """Loads the published survey results: one question row, many answer rows."""
    question_ids = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["question"] not in question_ids:
                cursor = conn.execute(
                    "INSERT INTO survey_questions (question_no, question, responses, note) VALUES (?, ?, ?, ?)",
                    (row["question_no"], row["question"], int(row["responses"]) if row["responses"] else None,
                     row["note"]),
                )
                question_ids[row["question"]] = cursor.lastrowid
            conn.execute(
                "INSERT INTO survey_answers (question_id, option, count, percent) VALUES (?, ?, ?, ?)",
                (question_ids[row["question"]], row["option"], int(row["count"]) if row["count"] else None,
                 float(row["percent"])),
            )
    return len(question_ids)


def load_sample_entries(conn, csv_path, category_ids):
    """Loads made-up tracker entries so the charts have something to show while testing."""
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cursor = conn.execute(
                "INSERT INTO respondents (age_group, gender, hours_per_day) VALUES (?, ?, ?)",
                (row["age_group"], row["gender"], float(row["hours_per_day"])),
            )
            conn.execute(
                """INSERT INTO purchases (respondent_id, category_id, product, amount_eur,
                                          influence, would_have_bought, regret, purchase_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cursor.lastrowid,
                    category_ids[row["category"]],
                    row["product"],
                    float(row["amount_eur"]),
                    row["influence"],
                    int(row["would_have_bought"]),
                    int(row["regret"]),
                    row["purchase_date"],
                ),
            )
            count += 1
    return count


def init_db(db_path=DB_PATH, research_csv=RESEARCH_CSV, sample_csv=None):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((BASE_DIR / "schema.sql").read_text())

    conn.executemany("INSERT INTO categories (name) VALUES (?)", [(c,) for c in CATEGORIES])
    category_ids = {name: cid for cid, name in conn.execute("SELECT category_id, name FROM categories")}

    questions = load_research(conn, research_csv) if research_csv else 0
    entries = load_sample_entries(conn, sample_csv, category_ids) if sample_csv else 0

    conn.commit()
    conn.close()
    return questions, entries


if __name__ == "__main__":
    use_sample = "--sample" in sys.argv
    questions, entries = init_db(sample_csv=SAMPLE_CSV if use_sample else None)
    print(f"Created {DB_PATH.name}: {questions} research questions, {entries} tracker entries.")
    if use_sample:
        print("WARNING: the tracker entries are made-up demo data. Don't report them as findings.")
