# Olist 巴西电商｜经营分析 & 履约体验洞察（MySQL + Python + PowerBI + Docker）

> **定位**：面向 *数据分析实习生 / 商业数据分析师（实习）* 的「可落地业务分析项目」。
> 
> **目标**：把 Kaggle 的 Olist 多表电商数据，按真实公司数据链路跑通：**落库 → 数仓/宽表 → KPI 分析 → PowerBI 看板**，并可直接发布到 GitHub 作为作品集。

---

## 为什么做这个项目

电商运营方最常见的困境不是没流量，而是**"单量看着不少，利润和口碑却上不来"**——问题出在哪个环节，没人说得清：是品类结构不行？履约太慢拖垮了评分？还是部分卖家在拖后腿？数据散在订单、支付、评价、卖家、商品等 9 张表里，口径互相对不上，任何回答都要现拼一次。

这个项目把"感觉卖不动"变成**可定位、可追踪的经营问题**：

1. **口径统一**——把 9 张散表整合成订单级 KPI 宽表，GMV、AOV、准时履约率、评分、支付结构从此只有一个版本；
2. **问题可定位**——沿品类、商家、履约环节三条线下钻，识别高贡献品类、慢履约订单与低评分商家的关联，把"口碑差"落到具体环节；
3. **结论可交付**——Python 自动生成经营报告，Power BI 看板让运营团队不用写 SQL 就能持续盯着自己该管的品类和卖家。

一句话：给电商经营装上一套**从数据到决策的仪表盘**，让每个"为什么"都能下钻到具体环节和卖家。

---

## 这个项目做了什么

| 环节 | 产出 |
| --- | --- |
| 数据建模 | 9 张业务表落 MySQL，构建订单级 KPI 宽表、类目月度趋势、商家评分卡三类分析视图 |
| ETL | Docker 化 Python 管道：分批导入、清洗、geolocation 按邮编前缀聚合 |
| 经营分析 | GMV、订单量、AOV、准时履约率、评分、支付结构、履约时效与差评的关系 |
| 可视化 | Python 自动生成图表与 Markdown 经营报告；Power BI 看板页面结构与 DAX 指标口径 |
| 工程化 | 数据字典、pipeline 流程图、Docker Compose 一键启动，全链路可复现 |

---

## 1. 项目亮点（写进简历的那种）
- **多源业务数据建模**：将 9 份 CSV（订单/明细/支付/评价/客户/卖家/商品/地理/类目）落库到 **MySQL**，构建可复用的分析视图（KPI 宽表、商家评分卡、履约时效分解等）。
- **完整分析闭环**：用 **Python** 生成可复现实验与结论（KPI、异常诊断、驱动因素分析），并自动输出图表与 Markdown 报告。
- **可视化交付**：提供 **PowerBI 看板设计方案**（页面结构 + DAX 指标口径），支持直连 MySQL 或使用导出 CSV。
- **工程化可复现**：用 **Docker Compose** 一键启动 MySQL + ETL/分析环境。

> 建议在简历里写成：
> - “基于 Olist 电商多表数据搭建 MySQL 分析库与 KPI 宽表，沉淀履约时效/评价/支付/商家绩效等指标体系；使用 Python 自动化生成经营周报与可视化图表，并在 PowerBI 构建经营看板（GMV/订单量/履约超时/差评率/商家评分卡）。”

---

## 2. 数据来源
- Kaggle：Brazilian E-Commerce Public Dataset by Olist
- 链接：<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/data>

### 数据文件清单（放在 `data/raw/`）
将以下 CSV 放入 `data/raw/`：
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_sellers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_geolocation_dataset.csv`
- `product_category_name_translation.csv`

> 注意：`olist_geolocation_dataset.csv` 约 100 万行，本项目默认在 ETL 时进行聚合（按 zip 前缀聚合）以加速分析。

---

## 3. 端到端流程图
```mermaid
flowchart TD
  A[下载 Kaggle CSV 放入 data/raw] --> B[Docker Compose 启动 MySQL]
  B --> C[Python ETL: 创建表/清洗/分批导入]
  C --> D[MySQL 生成分析视图
(vw_order_kpi / vw_seller_scorecard ...)]
  D --> E[Python 分析脚本
生成 reports/ 图表与结论]
  D --> F[PowerBI 连接 MySQL 视图
构建经营看板]
  E --> G[GitHub 发布：README + Docs + 报告样例]
  F --> G
```

---

## 4. 快速开始（本地一键跑通）
### 4.1 环境要求
- Docker Desktop / Docker Engine
- （可选）PowerBI Desktop（Windows）

### 4.2 一键启动 MySQL
```bash
docker compose up -d mysql
```

### 4.3 运行 ETL（建表 + 导入 + 生成视图）
```bash
# 第一次运行会创建数据库与表
docker compose run --rm etl python -m src.etl.load_to_mysql --all

# 创建分析视图
docker compose run --rm etl python -m src.etl.create_views
```

### 4.4 生成分析报告（可复现图表）
```bash
docker compose run --rm etl python -m src.analysis.generate_report
```
产出：
- `reports/eda_summary.md`
- `reports/figures/*.png`

---

## 5. PowerBI 看板（直连 MySQL）
### 5.1 连接方式
1. PowerBI Desktop → **获取数据** → **MySQL 数据库**
2. Server：`localhost`，Port：`3306`
3. Database：`olist`
4. 选择视图：
   - `vw_order_kpi`（订单级 KPI 宽表，强烈建议作为主事实表）
   - `vw_seller_scorecard`（商家评分卡）
   - `vw_category_monthly`（类目月度趋势）

> 若你电脑缺 MySQL 驱动，可使用 `src/analysis/export_for_powerbi.py` 导出 CSV，PowerBI 用“文本/CSV”导入即可。

### 5.2 建议的看板页面
详见 `powerbi/dashboard_spec.md`（包含指标口径与 DAX 模板）。

---

## 6. 目录结构
```
.
├─ data/
│  ├─ raw/                 # 放 Kaggle 原始 CSV（gitignore）
│  └─ processed/           # ETL 过程中生成的聚合文件（可选）
├─ sql/
│  ├─ 01_schema.sql        # MySQL 建表 DDL
│  └─ 02_views.sql         # 分析视图（宽表/评分卡/趋势表）
├─ src/
│  ├─ etl/
│  │  ├─ load_to_mysql.py  # 分批导入 + 清洗 + geolocation 聚合
│  │  └─ create_views.py   # 执行视图 SQL
│  ├─ analysis/
│  │  ├─ generate_report.py
│  │  └─ export_for_powerbi.py
│  └─ utils/
│     └─ db.py             # MySQL 连接与工具函数
├─ reports/
│  ├─ eda_summary.md
│  └─ figures/
├─ powerbi/
│  └─ dashboard_spec.md
└─ docs/
   ├─ learning_guide.tex    # Overleaf LaTeX 学习文档（可扩展方向）
   └─ resume_bullets.md     # 不同岗位版本简历 bullet 模板
```

---

## 7. 常见坑位（提前避雷）
- `customers` 表：同一自然人多次下单会出现多个 `customer_id`，复购/留存必须用 `customer_unique_id`。
- `payments` 表：同一订单可能多条支付记录，分析支付结构要按 `order_id` 汇总。
- `geolocation` 表：同一邮编前缀可能有多条坐标，本项目按 zip 前缀聚合（mean lat/lng + mode city/state）。

---

## 8. License
MIT
