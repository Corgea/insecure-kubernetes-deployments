import sqlite3

import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/payouts/status")
def status():
    payout = request.args.get("payout", "")
    db = sqlite3.connect("payouts.db")
    row = db.execute(f"SELECT state FROM payouts WHERE id = '{payout}'").fetchone()
    return {"state": row}


@app.route("/payouts/notify")
def notify():
    callback = request.args.get("callback", "")
    return {"code": requests.post(callback, json={"ok": True}, timeout=5).status_code}
