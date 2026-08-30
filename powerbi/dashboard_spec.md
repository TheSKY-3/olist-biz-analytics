# PowerBI 看板设计稿（Olist 电商经营分析）

推荐数据源：
- MySQL 视图 `vw_order_kpi`（订单级宽表）
- `vw_seller_scorecard`（商家评分卡）
- `vw_category_monthly`（类目月度趋势）

---

## 1) 页面结构（建议 4 到 5 页）

### Page 1：经营总览（Executive Overview）
目标：30 秒看懂业务规模与趋势。
- KPI 卡片：Orders、GMV、AOV、On-time Rate、Avg Review Score
- 折线：Monthly GMV、Monthly Orders
- 条形：Top 10 Categories by GMV
- 地图（可选）：按 Customer State 的 GMV 热力

### Page 2：履约时效（Fulfillment / SLA）
目标：拆解“慢在哪里”，定位治理方向。
- 指标卡：Avg Delay Days、Late Delivery Rate
- 堆叠柱：Delay Bucket（on_time / late 1-2 / late 3-5 / late 6+）占比
- 分布图：hrs_to_approve、hrs_to_carrier、hrs_purchase_to_delivered
- Top 列表：最慢 seller / 类目 / 州

### Page 3：口碑与差评驱动（Reviews）
目标：把口碑和履约/类目/卖家挂钩。
- 分布：review_score_avg 直方图
- 关联：Avg review score by delay bucket
- Top 列表：低评分 seller / 类目

### Page 4：商家评分卡（Seller Scorecard）
目标：对商家做分层管理。
- 表格：seller_id, orders, gmv, on_time_rate, avg_delay_days, avg_review_score
- 分层：按 on_time_rate + avg_review_score 分四象限（S/A/B/C）

### Page 5（可选）：支付结构（Payment）
- 支付方式占比（credit_card / boleto / voucher / debit_card）
- 分期数与 AOV 关系

---

## 2) 指标口径（建议用 DAX Measures）

假设主表命名为 `OrderKPI`（即 `vw_order_kpi` 导入后改名）。

### 2.1 核心经营指标
```DAX
Orders = COUNTROWS(OrderKPI)
GMV = SUM(OrderKPI[order_gmv])
AOV = DIVIDE([GMV], [Orders])
Avg Review = AVERAGE(OrderKPI[review_score_avg])
On-time Rate = AVERAGE(OrderKPI[is_on_time])
```

### 2.2 履约与延迟
```DAX
Late Orders = CALCULATE([Orders], OrderKPI[is_on_time] = 0)
Late Rate = DIVIDE([Late Orders], [Orders])
Avg Delay Days = AVERAGE(OrderKPI[days_delivery_delay])
```

### 2.3 差评率（可选）
```DAX
Bad Review Orders = CALCULATE([Orders], OrderKPI[review_score_avg] <= 2)
Bad Review Rate = DIVIDE([Bad Review Orders], [Orders])
```

---

## 3) 建议的筛选器（Slicers）
- 时间（月/季度）基于 `order_purchase_timestamp`
- 客户州：`customer_state`
- 订单状态：`order_status`（履约和口碑分析建议默认筛 `delivered`）
- 类目：来自 `vw_category_monthly`（或后续扩展订单-类目明细视图）

---

## 4) 可扩展方向（做成简历加分点）
- 增加“距离”特征：客户坐标 vs 卖家坐标（Haversine），分析距离对延迟与差评的影响
- 评论文本分析（NLP）：差评主题聚类（物流/破损/售后）
- 商家治理策略模拟：治理 Top X 慢商家，on-time rate 能提升多少
