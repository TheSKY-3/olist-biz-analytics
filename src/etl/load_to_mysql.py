"""ETL: load Olist raw CSVs into MySQL.

Usage:
  python -m src.etl.load_to_mysql --all

Expected raw files under data/raw/.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import text

from src.utils.db import mysql_engine, run_sql_file

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
SQL_DIR = Path("sql")

FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def _assert_files_exist():
    missing = [name for name, fn in FILES.items() if not (RAW_DIR / fn).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing raw CSV files in data/raw/: " + ", ".join(missing)
        )


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, **kwargs)


def _parse_datetime_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def build_geolocation_agg(raw_path: Path, out_path: Path) -> pd.DataFrame:
    """Aggregate geolocation by zip prefix.

    Strategy (initial, robust + simple):
    - lat/lng: mean
    - city/state: most frequent (mode) per prefix (computed via counters)

    This reduces ~1,000,000 rows to ~20k prefixes and makes MySQL + PowerBI faster.
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # streaming aggregation
    sum_lat: Dict[int, float] = {}
    sum_lng: Dict[int, float] = {}
    cnt: Dict[int, int] = {}
    city_state_counts: Dict[int, Dict[Tuple[str, str], int]] = {}

    chunks = pd.read_csv(raw_path, chunksize=200_000)
    for chunk in chunks:
        chunk = chunk.dropna(subset=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"])
        chunk["geolocation_zip_code_prefix"] = chunk["geolocation_zip_code_prefix"].astype(int)

        for row in chunk.itertuples(index=False):
            z = int(row.geolocation_zip_code_prefix)
            lat = float(row.geolocation_lat)
            lng = float(row.geolocation_lng)
            city = str(row.geolocation_city) if pd.notna(row.geolocation_city) else ""
            state = str(row.geolocation_state) if pd.notna(row.geolocation_state) else ""

            sum_lat[z] = sum_lat.get(z, 0.0) + lat
            sum_lng[z] = sum_lng.get(z, 0.0) + lng
            cnt[z] = cnt.get(z, 0) + 1

            if z not in city_state_counts:
                city_state_counts[z] = {}
            key = (city, state)
            city_state_counts[z][key] = city_state_counts[z].get(key, 0) + 1

    rows = []
    for z, n in cnt.items():
        mean_lat = sum_lat[z] / n
        mean_lng = sum_lng[z] / n
        # mode city/state
        cs_map = city_state_counts.get(z, {})
        (city, state), _ = max(cs_map.items(), key=lambda kv: kv[1]) if cs_map else (("", ""), 0)
        rows.append({
            "zip_code_prefix": z,
            "city": city,
            "state": state,
            "lat": round(mean_lat, 6),
            "lng": round(mean_lng, 6),
        })

    agg = pd.DataFrame(rows)
    agg.to_csv(out_path, index=False)
    return agg


def load_table(df: pd.DataFrame, table: str, engine, if_exists: str = "append"):
    df.to_sql(table, engine, if_exists=if_exists, index=False, chunksize=10_000, method="multi")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Load all tables")
    args = parser.parse_args()

    if not args.all:
        raise SystemExit("Please run with --all for the initial version.")

    _assert_files_exist()

    engine = mysql_engine(echo=False)

    # 1) create schema
    run_sql_file(engine, str(SQL_DIR / "01_schema.sql"))

    # 2) load dimension tables
    customers = _read_csv(RAW_DIR / FILES["customers"])
    load_table(customers, "customers", engine)

    sellers = _read_csv(RAW_DIR / FILES["sellers"])
    load_table(sellers, "sellers", engine)

    products = _read_csv(RAW_DIR / FILES["products"])
    load_table(products, "products", engine)

    cat = _read_csv(RAW_DIR / FILES["category_translation"])
    load_table(cat, "product_category_translation", engine)

    # 3) geolocation agg
    geo_agg_path = PROCESSED_DIR / "geolocation_agg.csv"
    if geo_agg_path.exists():
        geo_agg = _read_csv(geo_agg_path)
    else:
        geo_agg = build_geolocation_agg(RAW_DIR / FILES["geolocation"], geo_agg_path)
    load_table(geo_agg, "geolocation_agg", engine)

    # 4) orders + facts
    orders = _read_csv(RAW_DIR / FILES["orders"])
    orders = _parse_datetime_cols(
        orders,
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    load_table(orders, "orders", engine)

    items = _read_csv(RAW_DIR / FILES["order_items"])
    items = _parse_datetime_cols(items, ["shipping_limit_date"])
    load_table(items, "order_items", engine)

    payments = _read_csv(RAW_DIR / FILES["order_payments"])
    load_table(payments, "order_payments", engine)

    reviews = _read_csv(RAW_DIR / FILES["order_reviews"])
    reviews = _parse_datetime_cols(reviews, ["review_creation_date", "review_answer_timestamp"])
    load_table(reviews, "order_reviews", engine)

    # basic sanity checks
    with engine.connect() as conn:
        for t in ["orders","order_items","order_payments","order_reviews","customers","sellers","products","geolocation_agg","product_category_translation"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()
            print(f"Loaded {t}: {n:,}")


if __name__ == "__main__":
    main()
