"""
Example schemas for demonstration purposes
"""
import json
import os


def create_example_schemas():
    """Create example SQL schemas and mappings"""
    
    # Example: E-commerce migration (monolith → multi-tenant)
    
    old_schema = """-- Legacy E-commerce Database (Monolithic)
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
"""
    
    tenant_schema = """-- New Tenant Database Schema
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
"""
    
    central_schema = """-- Central Registry Database
-- Single database for cross-tenant analytics

CREATE TABLE sites_registry (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_uuid CHAR(36) UNIQUE NOT NULL,
    site_name VARCHAR(128) UNIQUE NOT NULL COMMENT 'Source: accounts.account_name',
    database_name VARCHAR(128) UNIQUE NOT NULL,
    created_at DATETIME COMMENT 'Source: accounts.created_at',
    is_active BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE user_registry (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_uuid CHAR(36) NOT NULL COMMENT 'Source: accounts.account_id',
    email VARCHAR(255) NOT NULL COMMENT 'Source: accounts.email',
    created_at DATETIME COMMENT 'Source: accounts.created_at',
    FOREIGN KEY (site_uuid) REFERENCES sites_registry(site_uuid)
) ENGINE=InnoDB;

CREATE TABLE order_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_uuid CHAR(36) NOT NULL,
    order_date DATE,
    total_orders INT,
    total_revenue DECIMAL(12,2),
    aggregated_at DATETIME,
    FOREIGN KEY (site_uuid) REFERENCES sites_registry(site_uuid)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_uuid CHAR(36) COMMENT 'Source: audit_log.account_id (via accounts)',
    site_name VARCHAR(128) COMMENT 'Source: accounts.account_name',
    action VARCHAR(255) COMMENT 'Source: audit_log.action',
    ip_address VARCHAR(45) COMMENT 'Source: audit_log.ip_address',
    timestamp DATETIME COMMENT 'Source: audit_log.timestamp',
    details TEXT COMMENT 'Source: audit_log.details',
    FOREIGN KEY (site_uuid) REFERENCES sites_registry(site_uuid)
) ENGINE=InnoDB;
"""
    
    field_mappings = {
        "_meta": {
            "version": "2.0.0",
            "description": "Example field mappings: E-commerce monolith → multi-tenant",
            "source": "Legacy monolithic database",
            "targets": ["Per-tenant databases", "Central registry database"]
        },
        "accounts": {
            "account_name": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "site",
                        "column": "site_name",
                        "sql": "SELECT account_name FROM accounts WHERE account_id = id AND internal_account = 0"
                    },
                    {
                        "db": "central",
                        "table": "sites_registry",
                        "column": "site_name",
                        "sql": "SELECT account_name FROM accounts WHERE account_id = id AND internal_account = 0"
                    }
                ]
            },
            "email": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "users",
                        "column": "email",
                        "sql": "SELECT email FROM accounts WHERE account_id = ? AND internal_account = 0"
                    },
                    {
                        "db": "central",
                        "table": "user_registry",
                        "column": "email",
                        "sql": "SELECT email FROM accounts WHERE internal_account = 0"
                    }
                ]
            },
            "password_hash": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "users",
                        "column": "password_hash",
                        "sql": "SELECT password_hash FROM accounts WHERE account_id = ?"
                    }
                ]
            },
            "is_admin": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "users",
                        "column": "is_admin",
                        "sql": "SELECT is_admin FROM accounts WHERE account_id = ?"
                    }
                ]
            },
            "created_at": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "site",
                        "column": "created_at",
                        "sql": "SELECT created_at FROM accounts WHERE account_id = id"
                    },
                    {
                        "db": "central",
                        "table": "sites_registry",
                        "column": "created_at",
                        "sql": "SELECT created_at FROM accounts WHERE account_id = id"
                    }
                ]
            }
        },
        "products": {
            "product_name": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "products",
                        "column": "product_name",
                        "sql": "SELECT product_name FROM products WHERE account_id = ?"
                    }
                ]
            },
            "description": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "products",
                        "column": "description",
                        "sql": "SELECT description FROM products WHERE account_id = ?"
                    }
                ]
            },
            "price": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "products",
                        "column": "price",
                        "sql": "SELECT price FROM products WHERE account_id = ?"
                    }
                ]
            }
        },
        "orders": {
            "account_id": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "orders",
                        "column": "user_id",
                        "sql": "SELECT account_id FROM orders WHERE account_id IN (SELECT id FROM accounts WHERE account_id = ?)"
                    }
                ]
            },
            "quantity": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "orders",
                        "column": "quantity",
                        "sql": "SELECT quantity FROM orders"
                    }
                ]
            },
            "total_amount": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "orders",
                        "column": "total_amount",
                        "sql": "SELECT total_amount FROM orders"
                    }
                ]
            }
        },
        "audit_log": {
            "action": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "audit_log",
                        "column": "action",
                        "sql": "SELECT action FROM audit_log WHERE account_id IN (SELECT id FROM accounts WHERE account_id = ?)"
                    },
                    {
                        "db": "central",
                        "table": "audit_log",
                        "column": "action",
                        "sql": "SELECT action FROM audit_log"
                    }
                ]
            },
            "ip_address": {
                "targets": [
                    {
                        "db": "tenant",
                        "table": "audit_log",
                        "column": "ip_address",
                        "sql": "SELECT ip_address FROM audit_log WHERE account_id IN (SELECT id FROM accounts WHERE account_id = ?)"
                    },
                    {
                        "db": "central",
                        "table": "audit_log",
                        "column": "ip_address",
                        "sql": "SELECT ip_address FROM audit_log"
                    }
                ]
            }
        },
        "_deprecated_tables": [
            "old_table_to_remove"
        ],
        "_deprecated_columns": {
            "accounts": ["internal_account"]
        }
    }
    
    # Write files
    os.makedirs("schemas/old", exist_ok=True)
    os.makedirs("schemas/new", exist_ok=True)
    os.makedirs("scripts", exist_ok=True)
    
    with open("schemas/old/schema.sql", "w") as f:
        f.write(old_schema)
    
    with open("schemas/new/tenant_schema.sql", "w") as f:
        f.write(tenant_schema)
    
    with open("schemas/new/central_schema.sql", "w") as f:
        f.write(central_schema)
    
    with open("scripts/field_mappings.json", "w") as f:
        json.dump(field_mappings, f, indent=2)
    
    print("  ✅ Created example schemas (E-commerce migration)")


