import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/shared/lookup")
def lookup():
    code = request.args.get("code", "")
    db = sqlite3.connect("shared.db")
    row = db.execute("SELECT label FROM codes WHERE code = '%s'" % code).fetchone()
    return {"label": row}
