"""TikTok Spending Tracker - Flask web app for LCCS ALT1.

Lets users Create, Read, Update and Delete (CRUD) purchases they made because of
TikTok, filter them, and see the results as Matplotlib charts.

Start it with:  python app.py   then open http://127.0.0.1:5050
"""
import math
import os
import secrets
import sqlite3
from datetime import date

from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, url_for

import charts
from init_db import DB_PATH, init_db

app = Flask(__name__)
app.config["DATABASE"] = DB_PATH
# Needed for flash messages. A random key is made each time the site starts, so it is never in the code
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

AGE_GROUPS = ["Under 16", "16-18", "19-21", "22-24", "25+"]
GENDERS = ["Female", "Male",]
INFLUENCES = ["Influencer review", "TikTok Shop", "Viral trend", "Paid ad", "Friend shared it"]
PER_PAGE = 20

# Only these columns can be sorted on, so the user can never inject SQL through ?sort=
SORT_OPTIONS = {
    "newest": ("Newest first", "p.purchase_date DESC"),
    "oldest": ("Oldest first", "p.purchase_date ASC"),
    "highest": ("Highest amount", "p.amount_eur DESC"),
    "lowest": ("Lowest amount", "p.amount_eur ASC"),
    "regret": ("Most regretted", "p.regret DESC"),
}

BASE_QUERY = """
    FROM purchases p
    JOIN respondents r ON r.respondent_id = p.respondent_id
    JOIN categories  c ON c.category_id   = p.category_id
"""


# ---------- Database helpers ----------

def get_db():
    """Open one database connection per request and reuse it."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # lets us use row["column_name"]
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_categories():
    return [row["name"] for row in get_db().execute("SELECT name FROM categories ORDER BY category_id")]


def build_filters(args):
    """Turn the filter dropdowns into a WHERE clause with ? placeholders."""
    clauses, params = [], []
    if args.get("age_group") in AGE_GROUPS:
        clauses.append("r.age_group = ?")
        params.append(args["age_group"])
    if args.get("category"):
        clauses.append("c.name = ?")
        params.append(args["category"])
    if args.get("influence") in INFLUENCES:
        clauses.append("p.influence = ?")
        params.append(args["influence"])
    if args.get("q", "").strip():
        clauses.append("p.product LIKE ?")
        params.append("%" + args["q"].strip() + "%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def validate(form):
    """Check the add/edit form. Returns (clean_data, list_of_errors)."""
    errors = []
    data = {
        "age_group": form.get("age_group", ""),
        "gender": form.get("gender", ""),
        "category": form.get("category", ""),
        "product": form.get("product", "").strip(),
        "influence": form.get("influence", ""),
        "would_have_bought": form.get("would_have_bought", ""),
        "regret": form.get("regret", ""),
        "purchase_date": form.get("purchase_date", ""),
        "hours_per_day": form.get("hours_per_day", "").strip(),
        "amount_eur": form.get("amount_eur", "").strip().replace("€", ""),
    }

    if data["age_group"] not in AGE_GROUPS:
        errors.append("Choose an age group.")
    if data["gender"] not in GENDERS:
        errors.append("Choose a gender option.")
    if data["category"] not in get_categories():
        errors.append("Choose a category.")
    if not data["product"]:
        errors.append("Enter what you bought.")
    elif len(data["product"]) > 60:
        errors.append("Keep the product name under 60 characters.")
    if data["influence"] not in INFLUENCES:
        errors.append("Choose how TikTok influenced you.")
    if data["would_have_bought"] not in ("0", "1"):
        errors.append("Say whether you would have bought it without TikTok.")
    if data["regret"] not in ("1", "2", "3", "4", "5"):
        errors.append("Choose a regret rating from 1 to 5.")

    try:
        data["hours_per_day"] = float(data["hours_per_day"])
        if not 0 <= data["hours_per_day"] <= 24:
            errors.append("Hours on TikTok per day must be between 0 and 24.")
    except ValueError:
        errors.append("Hours on TikTok per day must be a number, e.g. 2.5.")

    try:
        data["amount_eur"] = round(float(data["amount_eur"]), 2)
        if not math.isfinite(data["amount_eur"]):  # blocks "inf" and "nan"
            errors.append("Amount must be a number, e.g. 14.99.")
        elif data["amount_eur"] < 0:
            errors.append("Amount can't be negative.")
    except ValueError:
        errors.append("Amount must be a number, e.g. 14.99.")

    try:
        if date.fromisoformat(data["purchase_date"]) > date.today():
            errors.append("The purchase date can't be in the future.")
    except ValueError:
        errors.append("Enter a valid purchase date.")

    return data, errors


def form_options():
    return dict(
        age_groups=AGE_GROUPS,
        genders=GENDERS,
        influences=INFLUENCES,
        categories=get_categories(),
        today=date.today().isoformat(),
    )


# ---------- Pages ----------

@app.route("/")
def home():
    db = get_db()
    stats = db.execute(
        """SELECT COUNT(*)                         AS entries,
                  COALESCE(SUM(amount_eur), 0)     AS total,
                  COALESCE(AVG(amount_eur), 0)     AS average,
                  COALESCE(AVG(regret), 0)         AS regret,
                  COALESCE(AVG(1 - would_have_bought), 0) AS impulse
           FROM purchases"""
    ).fetchone()
    top_category = db.execute(
        "SELECT c.name, SUM(p.amount_eur) AS spent " + BASE_QUERY +
        "GROUP BY c.name ORDER BY spent DESC LIMIT 1"
    ).fetchone()
    recent = db.execute(
        "SELECT p.product, p.amount_eur, c.name AS category, p.purchase_date " + BASE_QUERY +
        "ORDER BY p.purchase_id DESC LIMIT 5"
    ).fetchall()
    # Headline figures from the published research, shown above the tracker's own numbers
    findings = db.execute(
        """SELECT q.question, a.option, a.percent FROM survey_answers a
           JOIN survey_questions q ON q.question_id = a.question_id
           WHERE q.question_no IN ('21', '22', '23')
           ORDER BY a.percent DESC"""
    ).fetchall()
    top_findings = {}
    for f in findings:
        top_findings.setdefault(f["question"], f)  # the highest answer for each question
    return render_template("home.html", stats=stats, top_category=top_category, recent=recent,
                           findings=list(top_findings.values()))


@app.route("/browse")
def browse():
    db = get_db()
    where, params = build_filters(request.args)
    sort = request.args.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"

    summary = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(p.amount_eur), 0) AS total " + BASE_QUERY + where, params
    ).fetchone()

    pages = max(1, -(-summary["n"] // PER_PAGE))  # round up
    page = min(max(request.args.get("page", 1, type=int), 1), pages)

    rows = db.execute(
        """SELECT p.purchase_id, p.product, p.amount_eur, p.influence, p.would_have_bought,
                  p.regret, p.purchase_date, c.name AS category, r.age_group """
        + BASE_QUERY + where + " ORDER BY " + SORT_OPTIONS[sort][1] + " LIMIT ? OFFSET ?",
        params + [PER_PAGE, (page - 1) * PER_PAGE],
    ).fetchall()

    # Keep the current filters when moving between pages
    filters = {k: v for k, v in request.args.items() if k != "page" and v}
    return render_template(
        "browse.html", rows=rows, summary=summary, page=page, pages=pages, filters=filters,
        sort=sort, sort_options=SORT_OPTIONS, **form_options()
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        data, errors = validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("form.html", entry=request.form, mode="add", **form_options()), 400

        db = get_db()
        cursor = db.execute(
            "INSERT INTO respondents (age_group, gender, hours_per_day) VALUES (?, ?, ?)",
            (data["age_group"], data["gender"], data["hours_per_day"]),
        )
        db.execute(
            """INSERT INTO purchases (respondent_id, category_id, product, amount_eur, influence,
                                      would_have_bought, regret, purchase_date)
               VALUES (?, (SELECT category_id FROM categories WHERE name = ?), ?, ?, ?, ?, ?, ?)""",
            (cursor.lastrowid, data["category"], data["product"], data["amount_eur"], data["influence"],
             int(data["would_have_bought"]), int(data["regret"]), data["purchase_date"]),
        )
        db.commit()
        flash(f"Thanks! Your entry for “{data['product']}” was added.", "success")
        return redirect(url_for("browse"))

    return render_template("form.html", entry={"purchase_date": date.today().isoformat()}, mode="add",
                           **form_options())


def fetch_entry(purchase_id):
    entry = get_db().execute(
        """SELECT p.*, c.name AS category, r.age_group, r.gender, r.hours_per_day """
        + BASE_QUERY + "WHERE p.purchase_id = ?",
        (purchase_id,),
    ).fetchone()
    if entry is None:
        abort(404)
    return entry


@app.route("/edit/<int:purchase_id>", methods=["GET", "POST"])
def edit(purchase_id):
    entry = fetch_entry(purchase_id)
    if request.method == "POST":
        data, errors = validate(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("form.html", entry=request.form, mode="edit", purchase_id=purchase_id,
                                   **form_options()), 400

        db = get_db()
        db.execute(
            "UPDATE respondents SET age_group = ?, gender = ?, hours_per_day = ? WHERE respondent_id = ?",
            (data["age_group"], data["gender"], data["hours_per_day"], entry["respondent_id"]),
        )
        db.execute(
            """UPDATE purchases
               SET category_id = (SELECT category_id FROM categories WHERE name = ?),
                   product = ?, amount_eur = ?, influence = ?, would_have_bought = ?,
                   regret = ?, purchase_date = ?
               WHERE purchase_id = ?""",
            (data["category"], data["product"], data["amount_eur"], data["influence"],
             int(data["would_have_bought"]), int(data["regret"]), data["purchase_date"], purchase_id),
        )
        db.commit()
        flash(f"Entry #{purchase_id} was updated.", "success")
        return redirect(url_for("browse"))

    return render_template("form.html", entry=entry, mode="edit", purchase_id=purchase_id, **form_options())


@app.route("/delete/<int:purchase_id>", methods=["GET", "POST"])
def delete(purchase_id):
    entry = fetch_entry(purchase_id)
    if request.method == "POST":
        db = get_db()
        # Deleting the respondent also deletes their purchase
        db.execute("DELETE FROM respondents WHERE respondent_id = ?", (entry["respondent_id"],))
        db.commit()
        flash(f"Entry #{purchase_id} (“{entry['product']}”) was deleted.", "success")
        return redirect(url_for("browse"))
    return render_template("delete.html", entry=entry)


@app.route("/charts")
def chart_page():
    age_group = request.args.get("age_group", "")
    if age_group not in AGE_GROUPS:
        age_group = ""
    where, params = build_filters({"age_group": age_group})
    db = get_db()

    # The same numbers are shown as tables under each chart for screen reader users
    tables = {
        "category": db.execute(
            "SELECT c.name AS label, ROUND(SUM(p.amount_eur), 2) AS value, COUNT(*) AS n " + BASE_QUERY + where +
            " GROUP BY c.name ORDER BY value DESC", params).fetchall(),
        "influence": db.execute(
            "SELECT p.influence AS label, COUNT(*) AS value " + BASE_QUERY + where +
            " GROUP BY p.influence ORDER BY value DESC", params).fetchall(),
        "age": db.execute(
            "SELECT r.age_group AS label, ROUND(AVG(p.amount_eur), 2) AS value, COUNT(*) AS n " + BASE_QUERY +
            " GROUP BY r.age_group ORDER BY CASE r.age_group WHEN 'Under 16' THEN 0 WHEN '16-18' THEN 1 "
            "WHEN '19-21' THEN 2 WHEN '22-24' THEN 3 ELSE 4 END").fetchall(),
        "regret": db.execute(
            "SELECT p.regret AS label, COUNT(*) AS value " + BASE_QUERY + where +
            " GROUP BY p.regret ORDER BY p.regret").fetchall(),
        "anyway": db.execute(
            "SELECT COALESCE(SUM(p.would_have_bought), 0) AS yes, COUNT(*) - COALESCE(SUM(p.would_have_bought), 0) AS no "
            + BASE_QUERY + where, params).fetchone(),
    }
    return render_template("charts.html", age_group=age_group, age_groups=AGE_GROUPS, tables=tables)


@app.route("/chart/<name>.png")
def chart_image(name):
    """Returns one chart as a PNG. The <img> tags on the charts page point here."""
    age_group = request.args.get("age_group", "")
    if age_group not in AGE_GROUPS:
        age_group = ""
    where, params = build_filters({"age_group": age_group})
    suffix = f" ({age_group})" if age_group else ""
    db = get_db()

    if name == "category":
        rows = db.execute("SELECT c.name, SUM(p.amount_eur) " + BASE_QUERY + where +
                          " GROUP BY c.name ORDER BY 2 DESC", params).fetchall()
        png = charts.bar_chart([r[0] for r in rows], [r[1] for r in rows],
                               "Total spent by category" + suffix, "Total spent (€)", "", money=True, horizontal=True)
    elif name == "influence":
        rows = db.execute("SELECT p.influence, COUNT(*) " + BASE_QUERY + where +
                          " GROUP BY p.influence ORDER BY 2 DESC", params).fetchall()
        png = charts.bar_chart([r[0] for r in rows], [r[1] for r in rows],
                               "What made people buy" + suffix, "Number of purchases", "", horizontal=True)
    elif name == "age":
        rows = db.execute("SELECT r.age_group, AVG(p.amount_eur) " + BASE_QUERY +
                          " GROUP BY r.age_group").fetchall()
        averages = dict((r[0], r[1]) for r in rows)
        labels = [a for a in AGE_GROUPS if a in averages]
        png = charts.bar_chart(labels, [averages[a] for a in labels],
                               "Average spend per purchase by age group", "Age group", "Average spend (€)", money=True)
    elif name == "regret":
        rows = dict(db.execute("SELECT p.regret, COUNT(*) " + BASE_QUERY + where +
                               " GROUP BY p.regret", params).fetchall())
        labels = ["1 – None", "2", "3", "4", "5 – A lot"] if rows else []
        png = charts.bar_chart(labels, [rows.get(i, 0) for i in range(1, 6)],
                               "How much people regretted it" + suffix, "Regret rating", "Number of purchases")
    elif name == "anyway":
        row = db.execute("SELECT COALESCE(SUM(p.would_have_bought), 0), COUNT(*) " + BASE_QUERY + where,
                         params).fetchone()
        png = charts.yes_no_chart(row[0], row[1] - row[0], "Would they have bought it without TikTok?" + suffix)
    else:
        abort(404)

    return send_file(png, mimetype="image/png", max_age=0)


@app.route("/research")
def research():
    """Shows the published DBS survey results stored in the database."""
    db = get_db()
    questions = db.execute(
        "SELECT * FROM survey_questions ORDER BY question_no = '?', CAST(question_no AS INTEGER)"
    ).fetchall()
    answers = {}
    images = {}
    for q in questions:
        answers[q["question_id"]] = db.execute(
            "SELECT option, count, percent FROM survey_answers WHERE question_id = ? ORDER BY answer_id",
            (q["question_id"],),
        ).fetchall()
        # Screenshot of the original chart from the source, if there is one (static/research/q21.png etc.)
        image = f"research/q{q['question_no']}.png"
        if (DB_PATH.parent / "static" / image).exists():
            images[q["question_id"]] = image
    return render_template("research.html", questions=questions, answers=answers, images=images)


@app.route("/about")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.template_filter("euro")
def euro(value):
    return "€{:,.2f}".format(value or 0)


# Build the database the first time the site starts (locally or on PythonAnywhere)
if not DB_PATH.exists():
    init_db()

if __name__ == "__main__":
    # debug=True only on your own computer; PythonAnywhere never runs this line
    app.run(debug=True, port=5050)  # 5000 is often used by AirPlay on Macs
