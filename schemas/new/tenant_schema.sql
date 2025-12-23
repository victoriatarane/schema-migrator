-- New Tenant Database Schema
-- One database per customer (isolated)

CREATE TABLE site (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_name VARCHAR(128) UNIQUE NOT NULL COMMENT 'Source: accounts.account_name',
    created_at DATETIME COMMENT 'Source: accounts.created_at',
    site_uuid CHAR(36) UNIQUE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(128) UNIQUE NOT NULL COMMENT 'Source: accounts.email',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'Source: accounts.email',
    password_hash VARCHAR(255) COMMENT 'Source: accounts.password_hash',
    is_admin BOOLEAN DEFAULT FALSE COMMENT 'Source: accounts.is_admin',
    created_at DATETIME COMMENT 'Source: accounts.created_at'
) ENGINE=InnoDB;

CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_name VARCHAR(255) COMMENT 'Source: products.product_name',
    description TEXT COMMENT 'Source: products.description',
    price DECIMAL(10,2) COMMENT 'Source: products.price',
    stock_quantity INT COMMENT 'Source: products.stock_quantity',
    created_at DATETIME COMMENT 'Source: products.created_at'
) ENGINE=InnoDB;

CREATE TABLE orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL COMMENT 'Source: orders.account_id',
    product_id INT NOT NULL COMMENT 'Source: orders.product_id',
    quantity INT COMMENT 'Source: orders.quantity',
    total_amount DECIMAL(10,2) COMMENT 'Source: orders.total_amount',
    status VARCHAR(50) COMMENT 'Source: orders.status',
    order_date DATETIME COMMENT 'Source: orders.order_date',
    shipped_date DATETIME COMMENT 'Source: orders.shipped_date',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;

CREATE TABLE payments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL COMMENT 'Source: payments.order_id',
    payment_method VARCHAR(50) COMMENT 'Source: payments.payment_method',
    amount DECIMAL(10,2) COMMENT 'Source: payments.amount',
    processed_at DATETIME COMMENT 'Source: payments.processed_at',
    FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT COMMENT 'Source: audit_log.account_id',
    action VARCHAR(255) COMMENT 'Source: audit_log.action',
    ip_address VARCHAR(45) COMMENT 'Source: audit_log.ip_address',
    timestamp DATETIME COMMENT 'Source: audit_log.timestamp',
    details TEXT COMMENT 'Source: audit_log.details',
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;
