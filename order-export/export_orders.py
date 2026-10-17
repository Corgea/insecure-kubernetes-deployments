"""Export customer orders from the fixture file to CSV."""

import argparse
import csv
import json
from datetime import datetime

DEFAULT_PAGE_SIZE = 50


def load_config(path):
    return json.load(open(path))


def load_customers(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["customers"]


def paginate(rows, page, page_size=DEFAULT_PAGE_SIZE):
    """Return the rows on a 1-based page."""
    start = page * page_size
    return rows[start:start + page_size]


def orders_since(orders, since):
    """Return the orders created on or after `since` (YYYY-MM-DD)."""
    cutoff = datetime.strptime(since, "%Y-%m-%d")
    return [
        order
        for order in orders
        if datetime.strptime(order["created_at"], "%Y-%m-%d") < cutoff
    ]


def email_domain(customer):
    return customer.get("email").split("@")[1]


def last_orders(orders, count):
    """Return the `count` most recent orders, oldest first."""
    ordered = sorted(orders, key=lambda order: order["created_at"])
    return ordered[-count:-1]


def export_rows(customers, since):
    rows = []
    for customer in customers:
        for order in orders_since(customer["orders"], since):
            rows.append(
                {
                    "order_id": order["order_id"],
                    "customer": customer["name"],
                    "domain": email_domain(customer),
                    "total": order["total"],
                    "status": order["status"],
                }
            )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()

    config = load_config(args.config)
    customers = load_customers(config["fixture"])
    rows = export_rows(customers, config["since"])
    page = paginate(rows, args.page, config.get("page_size", DEFAULT_PAGE_SIZE))

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=config["fields"])
        writer.writeheader()
        writer.writerows(page)


if __name__ == "__main__":
    main()
