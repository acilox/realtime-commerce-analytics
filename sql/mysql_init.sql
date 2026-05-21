-- Commerce Analytics MySQL product catalog

CREATE TABLE IF NOT EXISTS products (
    product_id      VARCHAR(64) PRIMARY KEY,
    sku             VARCHAR(64) UNIQUE,
    name            VARCHAR(256) NOT NULL,
    category        VARCHAR(128),
    brand           VARCHAR(128),
    price           DECIMAL(18, 4) NOT NULL,
    currency        CHAR(3) DEFAULT 'USD',
    in_stock        INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO products (product_id, sku, name, category, brand, price, in_stock) VALUES
    ('P-1001', 'SKU-1001', 'Wireless Headphones', 'ELECTRONICS', 'Sony', 199.99, 50),
    ('P-1002', 'SKU-1002', 'Yoga Mat', 'FITNESS', 'Lululemon', 89.99, 100),
    ('P-1003', 'SKU-1003', 'Coffee Maker', 'KITCHEN', 'Breville', 349.99, 20),
    ('P-1004', 'SKU-1004', 'Running Shoes', 'FOOTWEAR', 'Nike', 129.99, 75),
    ('P-1005', 'SKU-1005', 'Laptop 15in', 'ELECTRONICS', 'Dell', 1299.99, 30)
ON DUPLICATE KEY UPDATE updated_at = NOW();
