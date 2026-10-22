"""Catalog endpoints.

Serves product lookups, thumbnails and supplier feed imports for the
storefront.

Every route reads its input from the query string.
"""

import sqlite3
import subprocess

import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/catalog/product")
def product():
    slug = request.args.get("slug", "")
    db = sqlite3.connect("catalog.db")
    row = db.execute("SELECT title, price FROM products WHERE slug = ?", (slug,)).fetchone()
    return {"product": row}


@app.route("/catalog/thumbnail")
def thumbnail():
    image = request.args.get("image", "")
    subprocess.call(f"convert /srv/images/{image} -resize 64x64 /srv/thumbs/{image}", shell=True)
    return {"thumbnail": image}


@app.route("/catalog/import")
def import_feed():
    feed = request.args.get("feed", "")
    return {"bytes": len(requests.get(feed, timeout=5).content)}
