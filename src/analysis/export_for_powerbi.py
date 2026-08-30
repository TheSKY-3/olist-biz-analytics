"""Export key views to CSV for PowerBI import (fallback if MySQL connector is unavailable)."""

from pathlib import Path
import pandas as pd
from sqlalchemy import text

from src.utils.db import mysql_engine

OUT_DIR = Path("data/processed/powerbi_exports")

VIEWS = {
    "vw_order_kpi": "SELECT * FROM vw_order_kpi",
    "vw_seller_scorecard": "SELECT * FROM vw_seller_scorecard",
    "vw_category_monthly": "SELECT * FROM vw_category_monthly",
}


def main():
    engine = mysql_engine(echo=False)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, sql in VIEWS.items():
        df = pd.read_sql(text(sql), engine)
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        print(f"[OK] exported {name} -> {OUT_DIR/name}.csv")


if __name__ == "__main__":
    main()
