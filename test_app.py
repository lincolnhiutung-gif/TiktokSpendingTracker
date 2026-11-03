"""Automated tests for the TikTok Spending Tracker.

Run with:  python -m unittest test_app -v
Each test uses a fresh temporary copy of the database, so the real data is never touched.
"""
import os
import sqlite3
import tempfile
import unittest

from app import app
from init_db import init_db

VALID_ENTRY = {
    "age_group": "16-18",
    "gender": "Female",
    "hours_per_day": "3",
    "product": "Test lip oil",
    "category": "Beauty & Skincare",
    "amount_eur": "12.50",
    "purchase_date": "2026-01-15",
    "influence": "Influencer review",
    "would_have_bought": "0",
    "regret": "4",
}


class TrackerTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        init_db(self.db_path)  # research results only, no tracker entries
        app.config.update(DATABASE=self.db_path, TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def count(self, table="purchases"):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def add(self, **changes):
        return self.client.post("/add", data={**VALID_ENTRY, **changes}, follow_redirects=True)

    # --- Pages load ---
    def test_every_page_loads(self):
        for url in ["/", "/browse", "/add", "/charts", "/research", "/about"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_chart_images_are_png(self):
        self.add()
        for name in ["category", "influence", "age", "regret", "anyway"]:
            with self.subTest(chart=name):
                response = self.client.get(f"/chart/{name}.png")
                self.assertEqual(response.mimetype, "image/png")

    def test_research_results_loaded(self):
        page = self.client.get("/research").data.decode()
        self.assertIn("Why did you purchase?", page)
        self.assertIn("66.4%", page)
        self.assertIn("research/q21.png", page)  # source screenshot is shown
        self.assertEqual(self.client.get("/static/research/q21.png").status_code, 200)

    def test_research_percentages_match_counts(self):
        # Checks the typed-in figures: count / responses should equal the published %
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT a.option, a.count, a.percent, q.responses FROM survey_answers a
                   JOIN survey_questions q ON q.question_id = a.question_id
                   WHERE a.count IS NOT NULL""").fetchall()
        for option, count, percent, responses in rows:
            with self.subTest(option=option):
                self.assertAlmostEqual(count / responses * 100, percent, delta=0.1)

    # --- Create ---
    def test_add_valid_entry(self):
        response = self.add()
        self.assertIn(b"was added", response.data)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.count("respondents"), 1)

    def test_rejects_negative_amount(self):
        response = self.add(amount_eur="-5")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count(), 0)

    def test_rejects_text_amount(self):
        self.assertEqual(self.add(amount_eur="ten").status_code, 400)

    def test_rejects_too_many_hours(self):
        self.assertEqual(self.add(hours_per_day="25").status_code, 400)

    def test_rejects_future_date(self):
        self.assertEqual(self.add(purchase_date="2099-01-01").status_code, 400)

    def test_rejects_blank_product(self):
        self.assertEqual(self.add(product="   ").status_code, 400)

    def test_rejects_unknown_category(self):
        self.assertEqual(self.add(category="Cars").status_code, 400)

    def test_rejects_regret_out_of_range(self):
        self.assertEqual(self.add(regret="9").status_code, 400)

    # --- Read / filter ---
    def test_filter_by_age_group(self):
        self.add(product="Teen item", age_group="16-18")
        self.add(product="Adult item", age_group="25+")
        page = self.client.get("/browse?age_group=25%2B").data
        self.assertIn(b"Adult item", page)
        self.assertNotIn(b"Teen item", page)

    def test_search_is_safe_from_sql_injection(self):
        self.add()
        response = self.client.get("/browse?q=' OR 1=1; DROP TABLE purchases; --")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.count(), 1)  # table still exists and still has its row

    def test_bad_sort_falls_back_to_default(self):
        self.assertEqual(self.client.get("/browse?sort=DROP").status_code, 200)

    # --- Update ---
    def test_edit_entry(self):
        self.add()
        self.client.post("/edit/1", data={**VALID_ENTRY, "amount_eur": "99"})
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT amount_eur FROM purchases").fetchone()[0], 99)

    def test_edit_missing_entry_is_404(self):
        self.assertEqual(self.client.get("/edit/999").status_code, 404)

    # --- Delete ---
    def test_delete_entry_and_respondent(self):
        self.add()
        self.client.post("/delete/1")
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.count("respondents"), 0)

    def test_delete_needs_post(self):
        self.add()
        self.client.get("/delete/1")  # only shows the confirmation page
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
