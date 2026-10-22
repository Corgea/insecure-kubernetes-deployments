import sqlite3
import subprocess

import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/orders/find")
def find():
    reference = request.args.get("reference", "")
    db = sqlite3.connect("orders.db")
    row = db.execute("SELECT status FROM orders WHERE reference = ?", (reference,)).fetchone()
    return {"order": row}


def format_money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def summarize(lines):
    total = 0
    for line in lines:
        total += line["quantity"] * line["unit_cents"]
    return {"lines": len(lines), "total": format_money(total)}


def shipping_label(order):
    return "\n".join(
        [
            order["name"],
            order["street"],
            f"{order['postcode']} {order['city']}",
            order["country"],
        ]
    )


def is_international(order):
    return order["country"] not in ("US", "CA")


@app.route("/orders/export")
def export():
    month = request.args.get("month", "")
    subprocess.call(f"zip -r /srv/exports/{month}.zip /srv/orders/{month}", shell=True)
    return {"exported": month}


@app.route("/orders/callback")
def callback():
    url = request.args.get("url", "")
    return {"code": requests.get(url, timeout=5).status_code}
