import ipaddress
import os
import sqlite3
import subprocess

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)
DB_PATH = os.environ.get("ORDERS_DB", "orders.db")
EXPORT_DIR = "/srv/exports"
PAGE_SIZE = 20


def get_db():
    return sqlite3.connect(DB_PATH)


@app.route("/orders")
def list_orders():
    customer = request.args.get("customer", "")
    page = int(request.args.get("page", "1"))
    db = get_db()
    rows = db.execute(
        "SELECT id, customer, total FROM orders WHERE customer = ?", (customer,)
    ).fetchall()
    start = page * PAGE_SIZE
    return jsonify(rows[start : start + PAGE_SIZE])


@app.route("/ping")
def ping_warehouse():
    host = str(ipaddress.ip_address(request.args.get("host", "127.0.0.1")))
    result = subprocess.run(["ping", "-c", "1", host], capture_output=True)
    return jsonify({"reachable": result.returncode == 0})


@app.route("/export")
def download_export():
    name = request.args.get("name", "latest.csv")
    return send_file(os.path.join(EXPORT_DIR, name))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
