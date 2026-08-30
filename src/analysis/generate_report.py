"""Generate a lightweight, reproducible analysis report for the resume project.

Outputs:
- reports/eda_summary.md
- reports/figures/*.png

Focus on: business KPI, fulfillment, reviews, payment structure.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import text

from src.utils.db import mysql_engine

REPORTS_DIR = Path("reports")
FIG_DIR = REPORTS_DIR / "figures"


def query_df(engine, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


def save_fig(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main():
    engine = mysql_engine(echo=False)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Monthly GMV + Orders
    monthly = query_df(
        engine,
        """
        SELECT
          DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS month,
          COUNT(*) AS orders,
          SUM(order_gmv) AS gmv,
          AVG(order_gmv) AS aov
        FROM vw_order_kpi
        WHERE order_purchase_timestamp IS NOT NULL
        GROUP BY 1
        ORDER BY 1;
        """,
    )

    plt.figure()
    plt.plot(pd.to_datetime(monthly["month"]), monthly["gmv"])
    plt.title("Monthly GMV")
    plt.xlabel("Month")
    plt.ylabel("GMV")
    save_fig(FIG_DIR / "monthly_gmv.png")

    plt.figure()
    plt.plot(pd.to_datetime(monthly["month"]), monthly["orders"])
    plt.title("Monthly Orders")
    plt.xlabel("Month")
    plt.ylabel("Orders")
    save_fig(FIG_DIR / "monthly_orders.png")

    # 2) Delivery delay vs review score (delivered only)
    delay_review = query_df(
        engine,
        """
        SELECT
          CASE
            WHEN days_delivery_delay IS NULL THEN 'unknown'
            WHEN days_delivery_delay <= 0 THEN 'on_time_or_early'
            WHEN days_delivery_delay BETWEEN 1 AND 2 THEN 'late_1_2'
            WHEN days_delivery_delay BETWEEN 3 AND 5 THEN 'late_3_5'
            ELSE 'late_6_plus'
          END AS delay_bucket,
          AVG(review_score_avg) AS avg_review,
          COUNT(*) AS orders
        FROM vw_order_kpi
        WHERE order_status='delivered'
        GROUP BY 1
        ORDER BY orders DESC;
        """,
    )

    plt.figure()
    plt.bar(delay_review["delay_bucket"], delay_review["avg_review"])
    plt.title("Avg Review Score by Delivery Delay Bucket")
    plt.xlabel("Delay Bucket")
    plt.ylabel("Avg Review")
    plt.xticks(rotation=20, ha='right')
    save_fig(FIG_DIR / "review_by_delay.png")

    # 3) Payment type share (order-level)
    pay_share = query_df(
        engine,
        """
        SELECT
          SUM(has_credit_card) AS credit_card,
          SUM(has_boleto) AS boleto,
          SUM(has_voucher) AS voucher,
          SUM(has_debit_card) AS debit_card,
          COUNT(*) AS total_orders
        FROM vw_order_kpi;
        """,
    )
    s = pay_share.iloc[0].drop("total_orders")

    plt.figure()
    plt.bar(s.index, s.values)
    plt.title("Payment Type Presence (order-level)")
    plt.xlabel("Payment Type")
    plt.ylabel("Orders")
    plt.xticks(rotation=20, ha='right')
    save_fig(FIG_DIR / "payment_type_presence.png")

    # 4) Top categories by GMV
    top_cat = query_df(
        engine,
        """
        SELECT category, SUM(gmv) AS gmv
        FROM vw_category_monthly
        GROUP BY 1
        ORDER BY gmv DESC
        LIMIT 10;
        """,
    )
    plt.figure()
    plt.barh(top_cat["category"], top_cat["gmv"])
    plt.title("Top 10 Categories by GMV")
    plt.xlabel("GMV")
    plt.ylabel("Category")
    save_fig(FIG_DIR / "top_categories_gmv.png")

    # Write a compact markdown report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md = []
    md.append("# Olist 电商经营分析（自动生成报告）\n")
    md.append("## 核心KPI（按月）\n")
    md.append(monthly.tail(6).to_markdown(index=False))
    md.append("\n\n## 履约时效与口碑\n")
    md.append(delay_review.to_markdown(index=False))
    md.append("\n\n## 图表\n")
    for p in ["monthly_gmv.png","monthly_orders.png","review_by_delay.png","payment_type_presence.png","top_categories_gmv.png"]:
        md.append(f"![](figures/{p})")

    (REPORTS_DIR / "eda_summary.md").write_text("\n\n".join(md), encoding="utf-8")
    print("[OK] generated reports/eda_summary.md and figures")


if __name__ == "__main__":
    main()
