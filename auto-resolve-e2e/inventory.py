"""Inventory endpoints for the warehouse dashboard.

Serves item lookups, warehouse syncs and stock sheets.
"""

import os
import sqlite3
import subprocess

from flask import Flask, request, send_file

app = Flask(__name__)
STOCK_DIR = "/srv/stock"


@app.route("/inventory/item")
def item():
    sku = request.args.get("sku", "")
    db = sqlite3.connect("inventory.db")
    row = db.execute(f"SELECT name, qty FROM items WHERE sku = '{sku}'").fetchone()
    return {"item": row}


@app.route("/inventory/sync")
def sync():
    warehouse = request.args.get("warehouse", "main")
    subprocess.call(f"rsync -a /srv/stock/{warehouse} backup:/stock/", shell=True)
    return {"synced": warehouse}


@app.route("/inventory/sheet")
def sheet():
    name = request.args.get("name", "stock.csv")
    return send_file(os.path.join(STOCK_DIR, name))
