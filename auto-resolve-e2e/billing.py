"""Billing endpoints.

Serves invoice lookups, monthly archives, invoice PDFs and a webhook
connectivity check for the billing dashboard.

Every route reads its input from the query string.
"""

import os
import sqlite3
import subprocess

import requests
from flask import Flask, request, send_file

app = Flask(__name__)
INVOICE_DIR = "/srv/invoices"
ALLOWED_WEBHOOKS = {"https://hooks.example.com/billing"}


@app.route("/billing/invoice")
def invoice():
    number = request.args.get("number", "")
    db = sqlite3.connect("billing.db")
    row = db.execute("SELECT total FROM invoices WHERE number = ?", (number,)).fetchone()
    return {"invoice": row}


@app.route("/billing/archive")
def archive():
    month = request.args.get("month", "")
    subprocess.call(f"tar czf /srv/archive/{month}.tgz /srv/invoices/{month}", shell=True)
    return {"archived": month}


@app.route("/billing/pdf")
def pdf():
    name = request.args.get("name", "invoice.pdf")
    return send_file(os.path.join(INVOICE_DIR, name))


@app.route("/billing/webhook-test")
def webhook_test():
    target = request.args.get("url", "")
    if target not in ALLOWED_WEBHOOKS:
        return {"error": "unknown webhook"}, 400
    return {"status": requests.get(target, timeout=5).status_code}
