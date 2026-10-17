import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from export_orders import email_domain, last_orders, orders_since, paginate  # noqa: E402


def make_orders():
    return [
        {"order_id": "ORD-1", "created_at": "2026-01-05", "total": 10.0, "status": "shipped"},
        {"order_id": "ORD-2", "created_at": "2026-02-10", "total": 20.0, "status": "pending"},
        {"order_id": "ORD-3", "created_at": "2026-03-15", "total": 30.0, "status": "shipped"},
    ]


def test_paginate_first_page():
    rows = list(range(120))
    assert paginate(rows, 1, 50) == list(range(50))


def test_orders_since_keeps_newer_orders():
    since = orders_since(make_orders(), "2026-02-01")
    assert [order["order_id"] for order in since] == ["ORD-2", "ORD-3"]


def test_email_domain():
    assert email_domain({"email": "sample.customer@example.com"}) == "example.com"


def test_last_orders():
    assert len(last_orders(make_orders(), 2)) == 2
