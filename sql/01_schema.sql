-- MySQL schema for Olist dataset (raw layer)
-- Database is created by docker-compose env (MYSQL_DATABASE=olist)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS product_category_translation;
DROP TABLE IF EXISTS geolocation_agg;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
  order_id CHAR(32) PRIMARY KEY,
  customer_id CHAR(32) NOT NULL,
  order_status VARCHAR(20) NOT NULL,
  order_purchase_timestamp DATETIME NULL,
  order_approved_at DATETIME NULL,
  order_delivered_carrier_date DATETIME NULL,
  order_delivered_customer_date DATETIME NULL,
  order_estimated_delivery_date DATETIME NULL,
  KEY idx_orders_customer_id (customer_id),
  KEY idx_orders_purchase_ts (order_purchase_timestamp),
  KEY idx_orders_status (order_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_items (
  order_id CHAR(32) NOT NULL,
  order_item_id INT NOT NULL,
  product_id CHAR(32) NOT NULL,
  seller_id CHAR(32) NOT NULL,
  shipping_limit_date DATETIME NULL,
  price DECIMAL(10,2) NULL,
  freight_value DECIMAL(10,2) NULL,
  PRIMARY KEY (order_id, order_item_id),
  KEY idx_items_product_id (product_id),
  KEY idx_items_seller_id (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_payments (
  order_id CHAR(32) NOT NULL,
  payment_sequential INT NOT NULL,
  payment_type VARCHAR(20) NULL,
  payment_installments INT NULL,
  payment_value DECIMAL(10,2) NULL,
  PRIMARY KEY (order_id, payment_sequential),
  KEY idx_payments_type (payment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_reviews (
  review_id CHAR(32) NOT NULL,
  order_id CHAR(32) NOT NULL,
  review_score INT NULL,
  review_comment_title TEXT NULL,
  review_comment_message TEXT NULL,
  review_creation_date DATETIME NULL,
  review_answer_timestamp DATETIME NULL,
  PRIMARY KEY (review_id),
  KEY idx_reviews_order_id (order_id),
  KEY idx_reviews_score (review_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE customers (
  customer_id CHAR(32) PRIMARY KEY,
  customer_unique_id CHAR(32) NOT NULL,
  customer_zip_code_prefix INT NULL,
  customer_city VARCHAR(60) NULL,
  customer_state CHAR(2) NULL,
  KEY idx_customers_unique (customer_unique_id),
  KEY idx_customers_zip (customer_zip_code_prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sellers (
  seller_id CHAR(32) PRIMARY KEY,
  seller_zip_code_prefix INT NULL,
  seller_city VARCHAR(60) NULL,
  seller_state CHAR(2) NULL,
  KEY idx_sellers_zip (seller_zip_code_prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE products (
  product_id CHAR(32) PRIMARY KEY,
  product_category_name VARCHAR(80) NULL,
  product_name_lenght INT NULL,
  product_description_lenght INT NULL,
  product_photos_qty INT NULL,
  product_weight_g INT NULL,
  product_length_cm INT NULL,
  product_height_cm INT NULL,
  product_width_cm INT NULL,
  KEY idx_products_category (product_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Zip prefix is not unique in raw geolocation; we load an aggregated version.
CREATE TABLE geolocation_agg (
  zip_code_prefix INT PRIMARY KEY,
  city VARCHAR(60) NULL,
  state CHAR(2) NULL,
  lat DECIMAL(10,6) NULL,
  lng DECIMAL(10,6) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_category_translation (
  product_category_name VARCHAR(80) PRIMARY KEY,
  product_category_name_english VARCHAR(80) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
