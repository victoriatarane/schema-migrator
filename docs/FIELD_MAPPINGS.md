# Field Mapping Syntax

Complete reference for `field_mappings.json` configuration.

## Table of Contents

1. [Basic Structure](#basic-structure)
2. [Mapping Types](#mapping-types)
3. [SQL Query Syntax](#sql-query-syntax)
4. [Deprecation](#deprecation)
5. [Best Practices](#best-practices)
6. [Examples](#examples)

## Basic Structure

```json
{
  "_meta": { ... },
  "table_name": {
    "column_name": {
      "targets": [ ... ]
    }
  },
  "_deprecated_tables": [ ... ],
  "_deprecated_columns": { ... }
}
```

### File Format

- **Format**: JSON
- **Encoding**: UTF-8
- **Location**: `scripts/field_mappings.json`
- **Version**: 2.0.0 (multi-target support)

## Mapping Types

### 1. One-to-One Mapping

Single source → single destination:

```json
{
  "users": {
    "username": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "username",
          "sql": "SELECT username FROM users"
        }
      ]
    }
  }
}
```

### 2. One-to-Many Mapping

Single source → multiple destinations:

```json
{
  "users": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email",
          "sql": "SELECT email FROM users WHERE account_id = ?"
        },
        {
          "db": "central",
          "table": "user_registry",
          "column": "email",
          "sql": "SELECT email FROM users"
        }
      ]
    }
  }
}
```

### 3. Transformed Mapping

Apply transformation during migration:

```json
{
  "orders": {
    "total": {
      "targets": [
        {
          "db": "tenant",
          "table": "orders",
          "column": "total_cents",
          "sql": "SELECT ROUND(total * 100) FROM orders"
        }
      ]
    }
  }
}
```

### 4. Split Mapping

Split one column into multiple:

```json
{
  "users": {
    "full_name": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "first_name",
          "sql": "SELECT SUBSTRING_INDEX(full_name, ' ', 1) FROM users"
        },
        {
          "db": "tenant",
          "table": "users",
          "column": "last_name",
          "sql": "SELECT SUBSTRING_INDEX(full_name, ' ', -1) FROM users"
        }
      ]
    }
  }
}
```

### 5. Merge Mapping

Multiple sources → one destination:

```json
{
  "users": {
    "first_name": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "full_name",
          "sql": "SELECT CONCAT(first_name, ' ', last_name) FROM users"
        }
      ]
    }
  }
}
```

## Target Object Schema

```typescript
{
  db: "tenant" | "central",      // Required: Target database
  table: string,                  // Required: Target table name
  column: string,                 // Required: Target column name
  sql: string,                    // Optional: Migration SQL
  condition?: string,             // Optional: Filter condition
  transform?: string,             // Optional: Transformation description
  notes?: string                  // Optional: Additional notes
}
```

### Field Descriptions

#### `db` (required)
Which target database receives this field.

**Valid values**:
- `"tenant"` - Per-tenant database
- `"central"` - Central registry/analytics database

**Example**:
```json
"db": "tenant"
```

#### `table` (required)
Name of the target table.

**Rules**:
- Must exist in corresponding schema SQL file
- Case-sensitive
- No quotes needed

**Example**:
```json
"table": "users"
```

#### `column` (required)
Name of the target column.

**Rules**:
- Must exist in target table schema
- Case-sensitive
- No quotes needed

**Example**:
```json
"column": "email_address"
```

#### `sql` (optional but recommended)
SQL query for the migration.

**Purpose**:
- Documentation
- Code generation
- Validation

**Format**:
```json
"sql": "SELECT column FROM table WHERE condition"
```

**Placeholders**:
- `?` - For parameterized values
- `{}` - For template variables (e.g., `{tenant_id}`)

**Example**:
```json
"sql": "SELECT email FROM users WHERE tenant_id = ? AND active = 1"
```

## SQL Query Syntax

### Basic SELECT

```json
"sql": "SELECT username FROM users"
```

### With WHERE Clause

```json
"sql": "SELECT email FROM users WHERE active = 1"
```

### With Parameterized Values

```json
"sql": "SELECT email FROM users WHERE tenant_id = ? AND deleted_at IS NULL"
```

The `?` will be replaced with actual tenant ID during migration.

### With Transformations

#### String Operations
```json
"sql": "SELECT UPPER(username) FROM users"
"sql": "SELECT CONCAT(first_name, ' ', last_name) FROM users"
"sql": "SELECT SUBSTRING(phone, 1, 10) FROM users"
```

#### Numeric Operations
```json
"sql": "SELECT ROUND(amount * 1.1, 2) FROM orders"
"sql": "SELECT CAST(price AS DECIMAL(10,2)) FROM products"
```

#### Date Operations
```json
"sql": "SELECT DATE_FORMAT(created_at, '%Y-%m-%d') FROM users"
"sql": "SELECT UNIX_TIMESTAMP(updated_at) FROM orders"
```

#### Conditional Logic
```json
"sql": "SELECT CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END FROM users"
"sql": "SELECT IF(email_verified, email, NULL) FROM users"
```

#### Aggregations
```json
"sql": "SELECT COUNT(*) FROM orders GROUP BY user_id"
"sql": "SELECT SUM(amount) FROM transactions WHERE user_id = ?"
```

### With JOINs

```json
"sql": "SELECT u.email FROM users u JOIN accounts a ON u.account_id = a.id WHERE a.tenant_id = ?"
```

### Security Considerations

**Good** (parameterized):
```json
"sql": "SELECT email FROM users WHERE id = ?"
```

**Bad** (string concatenation):
```json
"sql": "SELECT email FROM users WHERE id = " + userId  // DON'T DO THIS
```

## Deprecation

### Deprecated Tables

Tables that won't be migrated:

```json
{
  "_deprecated_tables": [
    "temp_cache",
    "old_sessions",
    "migration_logs"
  ]
}
```

**Effect**:
- Table shown in diagram with red badge
- No mappings required for columns in these tables
- Marked as "Deprecated" in UI

### Deprecated Columns

Columns that won't be migrated:

```json
{
  "_deprecated_columns": {
    "users": ["legacy_password", "old_email"],
    "orders": ["temp_status", "deprecated_flag"],
    "products": ["unused_field"]
  }
}
```

**Effect**:
- Columns shown with strikethrough in diagram
- Reason displayed on hover
- Can add explanation in comment

### Adding Deprecation Reasons

```json
{
  "users": {
    "old_password": {
      "deprecated": true,
      "reason": "Replaced by bcrypt hashed passwords",
      "deprecated_date": "2024-01-15"
    }
  }
}
```

## Best Practices

### 1. Always Provide SQL

Even if obvious, SQL documentation is valuable:

**Good**:
```json
{
  "users": {
    "email": {
      "targets": [{
        "db": "tenant",
        "table": "users",
        "column": "email",
        "sql": "SELECT email FROM users WHERE tenant_id = ?"
      }]
    }
  }
}
```

**Bad**:
```json
{
  "users": {
    "email": {
      "targets": [{
        "db": "tenant",
        "table": "users",
        "column": "email"
      }]
    }
  }
}
```

### 2. Map Every Non-Deprecated Column

If a column isn't mapped and isn't deprecated, you'll get a warning.

### 3. Use Consistent Formatting

```json
{
  "table_name": {
    "column_name": {
      "targets": [
        {
          "db": "tenant",
          "table": "target_table",
          "column": "target_column",
          "sql": "SELECT column_name FROM table_name"
        }
      ]
    }
  }
}
```

### 4. Group Related Mappings

Keep related tables together:

```json
{
  "users": { ... },
  "user_profiles": { ... },
  "user_settings": { ... },
  
  "orders": { ... },
  "order_items": { ... },
  "order_payments": { ... }
}
```

### 5. Add Comments (as Notes)

```json
{
  "users": {
    "email": {
      "targets": [{
        "db": "tenant",
        "table": "users",
        "column": "email",
        "sql": "SELECT LOWER(TRIM(email)) FROM users WHERE email IS NOT NULL",
        "notes": "Normalize email: lowercase and trim whitespace"
      }]
    }
  }
}
```

### 6. Test SQL Queries

Before adding to mappings, test your SQL:

```sql
-- Test on actual database
SELECT CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END 
FROM users 
WHERE tenant_id = 123;
```

## Examples

### Example 1: E-commerce Multi-Tenant Migration

```json
{
  "_meta": {
    "version": "2.0.0",
    "description": "E-commerce monolith → multi-tenant",
    "source": "ecommerce_legacy",
    "targets": ["tenant_db_per_store", "central_analytics"]
  },
  
  "accounts": {
    "store_name": {
      "targets": [
        {
          "db": "tenant",
          "table": "store",
          "column": "name",
          "sql": "SELECT store_name FROM accounts WHERE account_id = id"
        },
        {
          "db": "central",
          "table": "stores_registry",
          "column": "store_name",
          "sql": "SELECT store_name FROM accounts WHERE account_id = id"
        }
      ]
    },
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "store",
          "column": "contact_email",
          "sql": "SELECT LOWER(TRIM(email)) FROM accounts"
        }
      ]
    }
  },
  
  "products": {
    "product_name": {
      "targets": [{
        "db": "tenant",
        "table": "products",
        "column": "name",
        "sql": "SELECT product_name FROM products WHERE account_id = ?"
      }]
    },
    "price": {
      "targets": [{
        "db": "tenant",
        "table": "products",
        "column": "price_cents",
        "sql": "SELECT ROUND(price * 100) FROM products WHERE account_id = ?",
        "notes": "Convert dollars to cents for precision"
      }]
    }
  },
  
  "_deprecated_tables": [
    "temp_cache",
    "old_sessions"
  ],
  
  "_deprecated_columns": {
    "accounts": ["legacy_password_hash"],
    "products": ["old_sku_format"]
  }
}
```

### Example 2: SaaS User Management

```json
{
  "users": {
    "full_name": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "first_name",
          "sql": "SELECT SUBSTRING_INDEX(full_name, ' ', 1) FROM users"
        },
        {
          "db": "tenant",
          "table": "users",
          "column": "last_name",
          "sql": "SELECT SUBSTRING_INDEX(full_name, ' ', -1) FROM users"
        }
      ]
    },
    "role": {
      "targets": [{
        "db": "tenant",
        "table": "users",
        "column": "role_id",
        "sql": "SELECT CASE role WHEN 'admin' THEN 1 WHEN 'user' THEN 2 ELSE 3 END FROM users"
      }]
    }
  }
}
```

### Example 3: Compliance-Safe Migration

```json
{
  "users": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email",
          "sql": "SELECT email FROM users WHERE tenant_id = ?",
          "notes": "PII - stays in tenant DB only"
        },
        {
          "db": "central",
          "table": "user_registry",
          "column": "email_hash",
          "sql": "SELECT SHA2(email, 256) FROM users",
          "notes": "Hashed for analytics (GDPR compliant)"
        }
      ]
    }
  }
}
```

## Validation

### Built-in Validation

```bash
schema-migrator validate
```

Checks:
- ✅ Valid JSON syntax
- ✅ All source tables exist in old schema
- ✅ All target tables exist in new schemas
- ✅ All columns exist in their respective tables
- ✅ No unmapped non-deprecated columns
- ✅ No duplicate mappings

### Manual Validation Checklist

- [ ] All tables from old schema are either mapped or deprecated
- [ ] All columns are either mapped or deprecated
- [ ] SQL queries are syntactically valid
- [ ] Transformations preserve data integrity
- [ ] Multi-target mappings don't create conflicts
- [ ] Sensitive data (PII) handled appropriately

## Common Patterns

### Pattern: Add Tenant Context

```json
"sql": "SELECT column FROM table WHERE tenant_id = ?"
```

### Pattern: Type Conversion

```json
"sql": "SELECT CAST(old_column AS NEW_TYPE) FROM table"
```

### Pattern: Default Values

```json
"sql": "SELECT COALESCE(column, 'default_value') FROM table"
```

### Pattern: Denormalization

```json
"sql": "SELECT JSON_OBJECT('key1', col1, 'key2', col2) FROM table"
```

### Pattern: Normalization

```json
"sql": "SELECT JSON_EXTRACT(data, '$.key') FROM table"
```

---

**Next**: [GitHub Integration](GITHUB_INTEGRATION.md)

