import sqlite3

import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/reports/search")
def search_reports():
    term = request.args.get("q", "")
    db = sqlite3.connect("reports.db")
    rows = db.execute(
        "SELECT title FROM reports WHERE title LIKE '%" + term + "%'"
    ).fetchall()
    return {"titles": [row[0] for row in rows]}


@app.route("/reports/preview")
def preview_report():
    source = request.args.get("url", "")
    return requests.get(source, timeout=5).text


@app.route("/reports/greeting")
def greeting():
    name = request.args.get("name", "there")
    return f"<h1>Report ready, {name}!</h1>"
