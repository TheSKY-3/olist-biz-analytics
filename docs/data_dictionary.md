# 数据字典（精简版）

> 本项目使用 9 份 Olist CSV，落库后对应表名见 `sql/01_schema.sql`。

## 1) orders（订单主表）
- order_id：订单ID（主键）
- customer_id：客户ID（与 customers.customer_id 关联）
- order_status：订单状态（delivered/canceled/...）
- order_purchase_timestamp：下单时间
- order_approved_at：支付批准时间
- order_delivered_carrier_date：交给承运商时间
- order_delivered_customer_date：客户签收时间
- order_estimated_delivery_date：预计送达时间

## 2) order_items（订单明细）
- order_id + order_item_id：复合主键
- product_id：商品ID
- seller_id：卖家ID
- shipping_limit_date：最晚发货时间
- price：商品价格
- freight_value：运费

## 3) order_payments（支付）
- order_id + payment_sequential：复合主键
- payment_type：支付方式
- payment_installments：分期数
- payment_value：支付金额

## 4) order_reviews（评价）
- review_id：评价ID（主键）
- order_id：订单ID
- review_score：评分（1-5）
- review_comment_title/message：文本
- review_creation_date：评论时间

## 5) customers（客户）
- customer_id：订单级客户ID（与 orders 直接关联）
- customer_unique_id：自然人ID（做复购/留存用它）
- zip/city/state：地理字段

## 6) sellers（卖家）
- seller_id：卖家ID
- zip/city/state：地理字段

## 7) products（商品）
- product_id：商品ID
- product_category_name：葡语类目
- 其他：商品属性（尺寸/重量/图片数量等）

## 8) geolocation_agg（地理聚合表）
- zip_code_prefix：邮编前缀（主键）
- lat/lng：聚合坐标（mean）
- city/state：聚合（mode）

## 9) product_category_translation（类目翻译）
- product_category_name → product_category_name_english
