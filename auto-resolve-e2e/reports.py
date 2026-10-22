import sqlite3
from urllib.parse import urlparse

import requests
from flask import Flask, request

app = Flask(__name__)
PREVIEW_HOSTS = {"reports.internal.example"}


@app.route("/reports/search")
def search_reports():
    term = request.args.get("q", "")
    db = sqlite3.connect("reports.db")
    rows = db.execute(
        "SELECT title FROM reports WHERE title LIKE ?", (f"%{term}%",)
    ).fetchall()
    return {"titles": [row[0] for row in rows]}


@app.route("/reports/preview")
def preview_report():
    report_id = request.args.get("id", "")
    if not report_id.isdigit():
        return {"error": "invalid report id"}, 400
    source = f"https://reports.internal.example/reports/{report_id}"
    assert urlparse(source).hostname in PREVIEW_HOSTS
    return requests.get(source, timeout=5).text


@app.route("/reports/greeting")
def greeting():
    name = request.args.get("name", "there")
    return f"<h1>Report ready, {name}!</h1>"
