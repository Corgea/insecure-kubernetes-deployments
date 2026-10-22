import yaml
from flask import Flask, request

app = Flask(__name__)


@app.route("/admin/calc", methods=["POST"])
def calculate():
    expression = request.form["expression"]
    return str(eval(expression))


@app.route("/admin/config", methods=["POST"])
def load_config():
    config = yaml.load(request.data, Loader=yaml.Loader)
    return {"keys": sorted(config)}
