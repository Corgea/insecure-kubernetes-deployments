#!/bin/sh
set -e

OUT_DIR=${1:-/tmp/order-exports}
CONFIG=order-export/config/export.json

mkdir -p $OUT_DIR
python3 order-export/export_orders.py --config $CONFIG --out $OUT_DIR/orders.csv
rm -f $OUT_DIR/*.tmp
echo "Export written to $OUT_DIR/orders.csv"
