# TikTok Spending Tracker (LCCS ALT1)

An interactive information system built with Python (Flask), SQLite and Matplotlib. It uses no JavaScript.

## Run it

```
pip install -r requirements.txt
python init_db.py      # optional: rebuilds the database (add --sample for 150 made-up demo entries)
python app.py          # open http://127.0.0.1:5050
```

Run the tests with `python -m unittest test_app -v`.

## Files

| File | What it does |
|---|---|
| `app.py` | Flask routes, SQL queries (CRUD), form validation |
| `schema.sql` | The three tables: `respondents`, `purchases`, `categories` |
| `init_db.py` | Creates the database and loads the CSV |
| `charts.py` | Matplotlib charts returned as PNG images |
| `templates/` | HTML pages (Jinja templates) |
| `static/style.css` | Responsive layout, dark mode, accessibility styles |
| `test_app.py` | 20 automated tests |
| `data/research_results.csv` | Published DBS survey results |
| `data/sample_responses.csv` | Made-up demo entries (testing only) |

## About the data

- `data/research_results.csv` holds the **real published results** from the Dublin Business School study
  (https://esource.dbs.ie/server/api/core/bitstreams/f845d8f0-73eb-49c6-9a6e-e63bbec971c5/content)
  (questions 21, 22 and 23, plus one 1-5 rating question whose title still needs to be filled in).
  Labels ending in "…" were cut short in the source charts.
- The tracker (Browse / Charts pages) **starts empty**. Fill it with real entries people add through the site.
- `data/sample_responses.csv` holds **150 made-up demo entries** for testing only. Load them with
  `python init_db.py --sample`. Don't report them as findings.
