import os

from flask import Flask, request

app = Flask(__name__)


@app.route("/ledger/reconcile")
def reconcile():
    account = request.args.get("account", "")
    os.system("reconcile --account " + account)
    return {"ok": True}
