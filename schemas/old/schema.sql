-- Legacy E-commerce Database (Monolithic)
-- Single database serving all customers

CREATE TABLE accounts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id INT NOT NULL COMMENT 'Parent account ID (self if primary)',
    account_name VARCHAR(128),
    email VARCHAR(255),
    password_hash VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at DATETIME,
    internal_account BOOLEAN DEFAULT FALSE COMMENT 'Internal test account'
) ENGINE=InnoDB;

CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id INT NOT NULL,
    product_name VARCHAR(255),
    description TEXT,
    price DECIMAL(10,2),
    stock_quantity INT,
    created_at DATETIME,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
) ENGINE=InnoDB;

CREATE TABLE orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT,
    total_amount DECIMAL(10,2),
    status VARCHAR(50),
    order_date DATETIME,
    shipped_date DATETIME,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;

CREATE TABLE payments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    payment_method VARCHAR(50),
    amount DECIMAL(10,2),
    processed_at DATETIME,
    FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    account_id INT,
    action VARCHAR(255),
    ip_address VARCHAR(45),
    timestamp DATETIME,
    details TEXT
) ENGINE=InnoDB;
