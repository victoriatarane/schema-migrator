-- Central Registry Database
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
