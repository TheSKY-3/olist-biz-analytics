"""Generate a self-contained interactive HTML business report from Olist CSVs.

Caliber ports sql/02_views.sql to pandas; key numbers are cross-checked against
reports/eda_summary.md (MySQL pipeline output) before the HTML is written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
VENDOR_JS = HERE / "vendor" / "echarts.min.js"
OUT_HTML = HERE.parents[1] / "docs" / "index.html"

PAY_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
BUCKET_ORDER = ["on_time_or_early", "late_1_2", "late_3_5", "late_6_plus"]
BUCKET_LABEL = {
    "on_time_or_early": "准时或提前",
    "late_1_2": "迟到 1-2 天",
    "late_3_5": "迟到 3-5 天",
    "late_6_plus": "迟到 6 天+",
    "unknown": "缺预计日期",
}

# reports/eda_summary.md（MySQL 管道产出）：month -> (orders, gmv, aov)
EXPECTED_MONTHLY = {
    "2018-05": (6873, 1.14978e6, 167.778),
    "2018-06": (6167, 1.02268e6, 166.019),
    "2018-07": (6292, 1.05873e6, 168.775),
    "2018-08": (6512, 1.00331e6, 155.503),
    "2018-09": (16, 166.46, 166.46),
    "2018-10": (4, None, None),
}
# bucket -> (avg_review, orders)
EXPECTED_DELAY = {
    "on_time_or_early": (4.29258, 89936),
    "late_1_2": (3.5178, 1370),
    "late_3_5": (2.46845, 1400),
    "late_6_plus": (1.73549, 3764),
    "unknown": (4.5, 8),
}


def load(data_dir: Path) -> dict:
    frames = {}
    for name in ["orders", "order_items", "order_payments", "order_reviews", "products", "product_category_name_translation"]:
        frames[name] = pd.read_csv(data_dir / f"olist_{name}_dataset.csv" if name != "product_category_name_translation" else data_dir / "product_category_name_translation.csv")
    # 原始 CSV 含 814 条重复 review_id；eda_summary 的公开数字对应去重后集合
    frames["order_reviews"] = frames["order_reviews"].drop_duplicates("review_id")
    o = frames["orders"]
    for col in ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        o[col] = pd.to_datetime(o[col])
    return frames


def bucket_of(d) -> str:
    if pd.isna(d):
        return "unknown"
    if d <= 0:
        return "on_time_or_early"
    if d <= 2:
        return "late_1_2"
    if d <= 5:
        return "late_3_5"
    return "late_6_plus"


def build(f: dict) -> dict:
    ia = f["order_items"].groupby("order_id").agg(items_value=("price", "sum"), freight_value=("freight_value", "sum"))
    ia["order_gmv"] = ia["items_value"] + ia["freight_value"]

    pf = f["order_payments"].copy()
    for t in PAY_TYPES:
        pf["has_" + t] = (pf["payment_type"] == t).astype(int)
    pa = pf.groupby("order_id")[["has_" + t for t in PAY_TYPES]].max()

    ra = f["order_reviews"].groupby("order_id")["review_score"].mean().rename("review_score_avg")

    kpi = f["orders"].merge(ia, on="order_id", how="left").merge(pa, on="order_id", how="left").merge(ra, on="order_id", how="left")
    # MySQL DATEDIFF 只比日期部分，这里用 normalize 对齐口径
    kpi["days_delivery_delay"] = (kpi["order_delivered_customer_date"].dt.normalize() - kpi["order_estimated_delivery_date"].dt.normalize()).dt.days

    monthly = (
        kpi[kpi["order_purchase_timestamp"].notna()]
        .assign(month=lambda d: d["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp())
        .groupby("month")
        .agg(orders=("order_id", "count"), gmv=("order_gmv", "sum"), aov=("order_gmv", "mean"))
        .reset_index()
    )

    delivered = kpi[kpi["order_status"] == "delivered"].copy()
    delivered["bucket"] = delivered["days_delivery_delay"].map(bucket_of)
    delay = delivered.groupby("bucket").agg(avg_review=("review_score_avg", "mean"), orders=("order_id", "count"))

    pay_counts = kpi[["has_" + t for t in PAY_TYPES]].sum()
    total_orders = len(kpi)

    oi = f["order_items"].merge(f["products"][["product_id", "product_category_name"]], on="product_id", how="left")
    oi = oi.merge(f["product_category_name_translation"], on="product_category_name", how="left")
    oi["category"] = oi["product_category_name_english"].fillna(oi["product_category_name"]).fillna("unknown")
    oi["gmv"] = oi["price"] + oi["freight_value"]
    # 不 join 评价表：多评价订单会在 join 后重复计 GMV（旧 vw_category_monthly 有此问题）
    top_cat = oi.groupby("category")["gmv"].sum().sort_values(ascending=False).head(10)

    known = delivered["days_delivery_delay"].notna()
    kpis = {
        "total_orders": int(total_orders),
        "gmv_total": float(kpi["order_gmv"].sum()),
        "aov": float(kpi["order_gmv"].mean()),
        "on_time_rate": float((delivered.loc[known, "days_delivery_delay"] <= 0).mean()),
        "avg_review": float(kpi["review_score_avg"].mean()),
        "window": [str(kpi["order_purchase_timestamp"].min().date()), str(kpi["order_purchase_timestamp"].max().date())],
    }
    return {"monthly": monthly, "delay": delay, "pay_counts": pay_counts, "total_orders": total_orders, "top_cat": top_cat, "kpis": kpis}


def crosscheck(m: dict) -> bool:
    rows = []
    ok = True

    def check(name, got, want, tol, rel=False):
        nonlocal ok
        if want is None:
            return
        good = (abs(got - want) / abs(want) <= tol) if rel else (abs(got - want) <= tol)
        ok &= good
        rows.append((name, got, want, "OK" if good else "FAIL"))

    for _, r in m["monthly"].iterrows():
        key = r["month"].strftime("%Y-%m")
        if key in EXPECTED_MONTHLY:
            eo, eg, ea = EXPECTED_MONTHLY[key]
            check(f"{key} orders", r["orders"], eo, 0)
            check(f"{key} gmv", r["gmv"], eg, 1e-4, rel=True)
            check(f"{key} aov", r["aov"], ea, 0.001)
    for b, (er, eo) in EXPECTED_DELAY.items():
        if b in m["delay"].index:
            check(f"{b} avg_review", m["delay"].loc[b, "avg_review"], er, 1e-4)
            check(f"{b} orders", m["delay"].loc[b, "orders"], eo, 0)
    print(f"{'check':<28}{'got':>14}{'want':>14}  result")
    for name, got, want, res in rows:
        print(f"{name:<28}{got:>14.5f}{want:>14.5f}  {res}")
    return ok


def render(m: dict) -> str:
    monthly = [
        {"month": r["month"].strftime("%Y-%m"), "orders": int(r["orders"]), "gmv": round(float(r["gmv"]), 2) if pd.notna(r["gmv"]) else None, "aov": round(float(r["aov"]), 2) if pd.notna(r["aov"]) else None}
        for _, r in m["monthly"].iterrows()
    ]
    delay = [
        {"bucket": b, "label": BUCKET_LABEL[b], "avg_review": round(float(m["delay"].loc[b, "avg_review"]), 2), "orders": int(m["delay"].loc[b, "orders"])}
        for b in BUCKET_ORDER + ["unknown"] if b in m["delay"].index
    ]
    pay = [{"type": t, "orders": int(m["pay_counts"]["has_" + t]), "share": round(100 * m["pay_counts"]["has_" + t] / m["total_orders"], 1)} for t in PAY_TYPES]
    top = [{"category": c, "gmv": round(float(v), 2)} for c, v in m["top_cat"].items()]
    payload = {"monthly": monthly, "delay": delay, "pay": pay, "top": top, "kpis": m["kpis"]}
    js = VENDOR_JS.read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = TEMPLATE.replace("__ECHARTS__", js).replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    return html


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist 电商经营分析 · 交互经营报告</title>
<style>
  :root { --ink:#1f2937; --mut:#6b7280; --bg:#f5f6f8; --card:#ffffff; --acc:#2563eb; --line:#e5e7eb; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif; background:var(--bg); color:var(--ink); line-height:1.6; }
  .wrap { max-width:1080px; margin:0 auto; padding:32px 20px 60px; }
  header h1 { font-size:26px; }
  header .sub { color:var(--mut); font-size:13px; margin-top:6px; }
  .headline { margin:22px 0; padding:16px 20px; background:var(--card); border-left:4px solid var(--acc); border-radius:6px; font-size:15px; }
  .headline b { color:var(--acc); }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:18px 0; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 16px; }
  .card .v { font-size:22px; font-weight:700; }
  .card .l { color:var(--mut); font-size:12px; margin-top:2px; }
  section { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:18px 20px; margin:16px 0; }
  section h2 { font-size:16px; margin-bottom:4px; }
  section .note { color:var(--mut); font-size:12px; margin-bottom:10px; }
  .chart { width:100%; height:360px; }
  table { border-collapse:collapse; width:100%; font-size:13px; margin-top:10px; }
  th,td { border:1px solid var(--line); padding:6px 10px; text-align:right; }
  th:first-child,td:first-child { text-align:left; }
  th { background:#f3f4f6; }
  footer { color:var(--mut); font-size:12px; margin-top:24px; }
  footer code { background:#eef1f4; padding:1px 5px; border-radius:4px; }
  a { color:var(--acc); }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Olist 电商经营分析 · 交互经营报告</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="headline">核心发现：<b>履约延迟是口碑的头号杀手</b> —— 准时或提前送达平均评分 <b id="h-on"></b>，迟到 6 天以上只剩 <b id="h-late"></b>。差评治理的抓手在履约时效，而非客服话术。</div>
<div class="cards" id="cards"></div>
<section><h2>月度 GMV 与订单量</h2><div class="note">2018-09 起为数据截断期（灰底标注），只展示、不作趋势结论。</div><div class="chart" id="c-monthly"></div></section>
<section><h2>履约延迟 × 平均评分</h2><div class="note">仅含 delivered 订单；延迟 = 送达日期 − 预计日期（日期差）。缺预计日期的 8 单归「缺预计日期」，不入图、见下表。</div><div class="chart" id="c-delay"></div><table id="t-delay"></table></section>
<section><h2>支付方式覆盖（订单级）</h2><div class="note">一单可含多种支付方式，占比合计可超 100%；分母为全部订单。</div><div class="chart" id="c-pay"></div></section>
<section><h2>Top 10 类目 GMV</h2><div class="note">类目 GMV 直接按订单明细汇总，不 join 评价表（多评价订单 join 后会重复计 GMV）。</div><div class="chart" id="c-top"></div></section>
<section><h2>口径与数据质量</h2>
  <table>
    <tr><th>项</th><th>口径</th></tr>
    <tr><td>GMV</td><td>商品价 + 运费，按 order_id 汇总（order_items）</td></tr>
    <tr><td>支付</td><td>先按 order_id 汇总再计占比，多支付订单不重复计单</td></tr>
    <tr><td>评分</td><td>先按订单取平均，再按延迟桶取平均</td></tr>
    <tr><td>评价去重</td><td>原始 CSV 含 814 条重复 review_id，按 review_id 去重后再按订单平均</td></tr>
    <tr><td>延迟桶</td><td>日期差 ≤0 / 1-2 / 3-5 / 6+，与 MySQL DATEDIFF 同口径</td></tr>
    <tr><td>复购 / 地理</td><td>复购按 customer_unique_id、地理按邮编前缀聚合（ETL 规则，本报告未展示）</td></tr>
    <tr><td>截断期</td><td>2018-09 起订单不完整，不下「GMV 下滑」类结论</td></tr>
  </table>
</section>
<footer>
  <a href="https://github.com/TheSKY-3/olist-biz-analytics">GitHub 仓库</a> · 数据：Kaggle Olist 公开数据集（CC BY-NC-SA 4.0）
</footer>
</div>
<script>__ECHARTS__</script>
<script>
const D = __DATA__;
const fmt = n => n == null ? '—' : n.toLocaleString('zh-CN');
document.getElementById('sub').textContent = '数据窗口 ' + D.kpis.window[0] + ' ~ ' + D.kpis.window[1] + ' · 9 张业务表 · 口径见文末';
const on = D.delay.find(x => x.bucket === 'on_time_or_early');
const late = D.delay.find(x => x.bucket === 'late_6_plus');
document.getElementById('h-on').textContent = on.avg_review.toFixed(2);
document.getElementById('h-late').textContent = late.avg_review.toFixed(2);
const cards = [
  [fmt(D.kpis.total_orders), '订单总量'],
  ['R$ ' + (D.kpis.gmv_total / 1e6).toFixed(2) + 'M', 'GMV（商品+运费）'],
  ['R$ ' + D.kpis.aov.toFixed(1), '客单价 AOV'],
  [(D.kpis.on_time_rate * 100).toFixed(1) + '%', '准时履约率（delivered）'],
  [D.kpis.avg_review.toFixed(2), '平均评分（订单级）'],
];
document.getElementById('cards').innerHTML = cards.map(c => '<div class="card"><div class="v">' + c[0] + '</div><div class="l">' + c[1] + '</div></div>').join('');
const charts = [];
function mk(id, opt) { const c = echarts.init(document.getElementById(id)); c.setOption(opt); charts.push(c); }
const mut = '#6b7280', line = '#e5e7eb';
mk('c-monthly', {
  tooltip: { trigger: 'axis' },
  legend: { data: ['GMV', '订单量'], textStyle: { color: mut } },
  grid: { left: 70, right: 60, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: D.monthly.map(x => x.month), axisLabel: { color: mut } },
  yAxis: [
    { type: 'value', name: 'GMV (R$)', axisLabel: { color: mut, formatter: v => (v / 1e6).toFixed(1) + 'M' }, splitLine: { lineStyle: { color: line } } },
    { type: 'value', name: '订单量', axisLabel: { color: mut }, splitLine: { show: false } }
  ],
  series: [
    { name: 'GMV', type: 'bar', data: D.monthly.map(x => x.gmv), itemStyle: { color: '#2563eb' },
      markArea: { silent: true, itemStyle: { color: 'rgba(107,114,128,0.12)' }, label: { color: mut, position: 'insideTop' }, data: [[{ name: '数据截断期', xAxis: '2018-09' }, { xAxis: D.monthly[D.monthly.length - 1].month }]] } },
    { name: '订单量', type: 'line', yAxisIndex: 1, data: D.monthly.map(x => x.orders), itemStyle: { color: '#f59e0b' }, smooth: true }
  ]
});
const dl = D.delay.filter(x => x.bucket !== 'unknown');
mk('c-delay', {
  tooltip: { trigger: 'axis' },
  legend: { data: ['订单量', '平均评分'], textStyle: { color: mut } },
  grid: { left: 70, right: 60, top: 40, bottom: 40 },
  xAxis: { type: 'category', data: dl.map(x => x.label), axisLabel: { color: mut } },
  yAxis: [
    { type: 'value', name: '订单量', axisLabel: { color: mut }, splitLine: { lineStyle: { color: line } } },
    { type: 'value', name: '平均评分', min: 0, max: 5, axisLabel: { color: mut }, splitLine: { show: false } }
  ],
  series: [
    { name: '订单量', type: 'bar', data: dl.map(x => x.orders), itemStyle: { color: '#93c5fd' } },
    { name: '平均评分', type: 'line', yAxisIndex: 1, data: dl.map(x => x.avg_review), itemStyle: { color: '#dc2626' }, label: { show: true, formatter: p => p.value.toFixed(2) } }
  ]
});
document.getElementById('t-delay').innerHTML = '<tr><th>延迟桶</th><th>平均评分</th><th>订单量</th></tr>' + D.delay.map(x => '<tr><td>' + x.label + '</td><td>' + x.avg_review.toFixed(2) + '</td><td>' + fmt(x.orders) + '</td></tr>').join('');
mk('c-pay', {
  tooltip: { trigger: 'axis', formatter: ps => ps[0].name + '：' + fmt(D.pay[ps[0].dataIndex].orders) + ' 单（' + ps[0].value + '%）' },
  grid: { left: 70, right: 30, top: 30, bottom: 40 },
  xAxis: { type: 'category', data: D.pay.map(x => x.type), axisLabel: { color: mut } },
  yAxis: { type: 'value', name: '占订单 %', axisLabel: { color: mut }, splitLine: { lineStyle: { color: line } } },
  series: [{ type: 'bar', data: D.pay.map(x => x.share), itemStyle: { color: '#2563eb' }, label: { show: true, position: 'top', formatter: p => p.value + '%' } }]
});
mk('c-top', {
  tooltip: { trigger: 'axis', formatter: ps => ps[0].name + '：R$ ' + fmt(Math.round(ps[0].value)) },
  grid: { left: 130, right: 60, top: 20, bottom: 40 },
  xAxis: { type: 'value', axisLabel: { color: mut, formatter: v => (v / 1e6).toFixed(1) + 'M' }, splitLine: { lineStyle: { color: line } } },
  yAxis: { type: 'category', inverse: true, data: D.top.map(x => x.category), axisLabel: { color: mut } },
  series: [{ type: 'bar', data: D.top.map(x => x.gmv), itemStyle: { color: '#2563eb' } }]
});
window.addEventListener('resize', () => charts.forEach(c => c.resize()));
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, type=Path)
    args = ap.parse_args()
    m = build(load(args.data_dir))
    if not crosscheck(m):
        print("[FAIL] 数字与 eda_summary 不一致，不写 HTML")
        sys.exit(1)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(render(m), encoding="utf-8")
    print(f"[OK] wrote {OUT_HTML} ({OUT_HTML.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
