-- Analytics views (semantic layer)
SET NAMES utf8mb4;

-- 1) Order-level aggregation from order_items
DROP VIEW IF EXISTS vw_order_item_agg;
CREATE VIEW vw_order_item_agg AS
SELECT
  oi.order_id,
  COUNT(*) AS item_cnt,
  COUNT(DISTINCT oi.product_id) AS sku_cnt,
  COUNT(DISTINCT oi.seller_id) AS seller_cnt,
  SUM(oi.price) AS items_value,
  SUM(oi.freight_value) AS freight_value
FROM order_items oi
GROUP BY oi.order_id;

-- 2) Payment aggregation per order
DROP VIEW IF EXISTS vw_order_payment_agg;
CREATE VIEW vw_order_payment_agg AS
SELECT
  p.order_id,
  SUM(p.payment_value) AS payment_value,
  MAX(p.payment_installments) AS max_installments,
  COUNT(*) AS payment_txn_cnt,
  MAX(CASE WHEN p.payment_type='credit_card' THEN 1 ELSE 0 END) AS has_credit_card,
  MAX(CASE WHEN p.payment_type='boleto' THEN 1 ELSE 0 END) AS has_boleto,
  MAX(CASE WHEN p.payment_type='voucher' THEN 1 ELSE 0 END) AS has_voucher,
  MAX(CASE WHEN p.payment_type='debit_card' THEN 1 ELSE 0 END) AS has_debit_card
FROM order_payments p
GROUP BY p.order_id;

-- 3) Review aggregation per order
DROP VIEW IF EXISTS vw_order_review_agg;
CREATE VIEW vw_order_review_agg AS
SELECT
  r.order_id,
  AVG(r.review_score) AS review_score_avg,
  MAX(r.review_score) AS review_score_max,
  MIN(r.review_score) AS review_score_min,
  COUNT(*) AS review_cnt
FROM order_reviews r
GROUP BY r.order_id;

-- 4) Order KPI wide table (recommended as PowerBI fact)
DROP VIEW IF EXISTS vw_order_kpi;
CREATE VIEW vw_order_kpi AS
SELECT
  o.order_id,
  o.order_status,
  o.order_purchase_timestamp,
  o.order_approved_at,
  o.order_delivered_carrier_date,
  o.order_delivered_customer_date,
  o.order_estimated_delivery_date,
  o.customer_id,
  c.customer_unique_id,
  c.customer_city,
  c.customer_state,
  c.customer_zip_code_prefix,
  ca.lat AS customer_lat,
  ca.lng AS customer_lng,

  ia.item_cnt,
  ia.sku_cnt,
  ia.seller_cnt,
  ia.items_value,
  ia.freight_value,
  (ia.items_value + ia.freight_value) AS order_gmv,

  pa.payment_value,
  pa.max_installments,
  pa.payment_txn_cnt,
  pa.has_credit_card,
  pa.has_boleto,
  pa.has_voucher,
  pa.has_debit_card,

  ra.review_score_avg,
  ra.review_cnt,

  -- fulfillment lead times (hours)
  TIMESTAMPDIFF(HOUR, o.order_purchase_timestamp, o.order_approved_at) AS hrs_to_approve,
  TIMESTAMPDIFF(HOUR, o.order_approved_at, o.order_delivered_carrier_date) AS hrs_to_carrier,
  TIMESTAMPDIFF(HOUR, o.order_delivered_carrier_date, o.order_delivered_customer_date) AS hrs_carrier_to_customer,
  TIMESTAMPDIFF(HOUR, o.order_purchase_timestamp, o.order_delivered_customer_date) AS hrs_purchase_to_delivered,
  DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) AS days_delivery_delay,
  CASE
    WHEN o.order_delivered_customer_date IS NULL OR o.order_estimated_delivery_date IS NULL THEN NULL
    WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1
    ELSE 0
  END AS is_on_time
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN geolocation_agg ca ON c.customer_zip_code_prefix = ca.zip_code_prefix
LEFT JOIN vw_order_item_agg ia ON o.order_id = ia.order_id
LEFT JOIN vw_order_payment_agg pa ON o.order_id = pa.order_id
LEFT JOIN vw_order_review_agg ra ON o.order_id = ra.order_id;

-- 5) Monthly category trend (for dashboard)
DROP VIEW IF EXISTS vw_category_monthly;
CREATE VIEW vw_category_monthly AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m-01') AS month,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
  COUNT(DISTINCT o.order_id) AS orders,
  SUM(oi.price + oi.freight_value) AS gmv,
  AVG(r.review_score) AS avg_review_score
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_category_translation t ON p.product_category_name = t.product_category_name
LEFT JOIN order_reviews r ON o.order_id = r.order_id
WHERE o.order_purchase_timestamp IS NOT NULL
GROUP BY 1,2;

-- 6) Seller scorecard (seller-level performance)
DROP VIEW IF EXISTS vw_seller_scorecard;
CREATE VIEW vw_seller_scorecard AS
SELECT
  s.seller_id,
  s.seller_city,
  s.seller_state,
  sa.lat AS seller_lat,
  sa.lng AS seller_lng,
  COUNT(DISTINCT o.order_id) AS orders,
  SUM(oi.price + oi.freight_value) AS gmv,
  AVG(vk.days_delivery_delay) AS avg_delay_days,
  AVG(vk.is_on_time) AS on_time_rate,
  AVG(vk.review_score_avg) AS avg_review_score
FROM sellers s
LEFT JOIN geolocation_agg sa ON s.seller_zip_code_prefix = sa.zip_code_prefix
JOIN order_items oi ON s.seller_id = oi.seller_id
JOIN orders o ON oi.order_id = o.order_id
LEFT JOIN vw_order_kpi vk ON o.order_id = vk.order_id
GROUP BY 1,2,3,4,5;
