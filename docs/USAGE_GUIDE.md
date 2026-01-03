# Schema Migrator - Complete Usage Guide

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Field Mappings](#field-mappings)
5. [GitHub Integration](#github-integration)
6. [Customization](#customization)
7. [Advanced Features](#advanced-features)

## Installation

### From PyPI (when published)

```bash
pip install schema-migrator
```

### From Source

```bash
git clone https://github.com/victoriatarane/schema-migrator.git
cd schema-migrator
pip install -e .
```

## Quick Start

### 1. Initialize a New Project

```bash
schema-migrator init
```

This creates:
```
your-project/
├── schemas/
│   ├── old/
│   │   └── schema.sql        # Your legacy schema
│   └── new/
│       ├── tenant_schema.sql  # New per-tenant schema
│       └── central_schema.sql # Central registry schema
├── scripts/
│   └── field_mappings.json    # Field migration mappings
├── tools/                      # Generated diagrams go here
└── docs/                       # Your documentation
```

### 2. Add Your Schemas

Replace the example schemas with your actual schemas:

**schemas/old/schema.sql:**
```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    username VARCHAR(100),
    email VARCHAR(255),
    created_at DATETIME
) ENGINE=InnoDB;
```

**schemas/new/tenant_schema.sql:**
```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    username VARCHAR(100) COMMENT 'Source: users.username',
    email VARCHAR(255) COMMENT 'Source: users.email',
    created_at DATETIME COMMENT 'Source: users.created_at'
) ENGINE=InnoDB;
```

### 3. Define Field Mappings

Edit `scripts/field_mappings.json`:

```json
{
  "_meta": {
    "version": "2.0.0",
    "description": "My migration mappings"
  },
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

### 4. Build the Diagram

```bash
schema-migrator build
```

### 5. Open the Diagram

```bash
open tools/schema_diagram.html
```

## Project Structure

### Recommended Structure

```
your-migration-project/
├── .git/                       # Git repository
├── .github/
│   └── ISSUE_TEMPLATE/         # Issue templates for discussions
├── schemas/
│   ├── old/
│   │   └── schema.sql          # Legacy schema dump
│   └── new/
│       ├── tenant_schema.sql   # Per-tenant database schema
│       └── central_schema.sql  # Central registry schema (optional)
├── scripts/
│   ├── field_mappings.json     # **CRITICAL** - Field migration logic
│   └── migrate.py              # Optional: actual migration script
├── tools/
│   └── schema_diagram.html     # Generated interactive diagram
├── docs/
│   ├── MIGRATION_PLAN.md
│   └── DECISIONS.md
├── .gitignore
└── README.md
```

### Internal vs Public Repos

**For Internal Use** (private repo with proprietary schemas):
```
your-company/migration-internal/
├── schemas/
│   ├── old/
│   │   └── production_schema.sql  # Real production schema
│   └── new/
│       ├── tenant_schema.sql
│       └── central_schema.sql
└── scripts/
    └── field_mappings.json         # Real mappings
```

**For Public Portfolio** (public repo with example schemas):
```
your-github/schema-migrator/
├── schemas/
│   ├── old/
│   │   └── schema.sql             # Example: e-commerce
│   └── new/
│       ├── tenant_schema.sql
│       └── central_schema.sql
└── scripts/
    └── field_mappings.json        # Example mappings
```

## Field Mappings

### Basic Mapping

Single source → single target:

```json
{
  "old_table": {
    "old_column": {
      "targets": [
        {
          "db": "tenant",
          "table": "new_table",
          "column": "new_column",
          "sql": "SELECT old_column FROM old_table"
        }
      ]
    }
  }
}
```

### Multi-Target Mapping

Single source → multiple targets (e.g., tenant DB + central DB):

```json
{
  "users": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email",
          "sql": "SELECT email FROM users WHERE tenant_id = ?"
        },
        {
          "db": "central",
          "table": "user_registry",
          "column": "email_hash",
          "sql": "SELECT SHA2(email, 256) FROM users"
        }
      ]
    }
  }
}
```

### Deprecated Fields

Mark fields that won't be migrated:

```json
{
  "_deprecated_tables": [
    "old_unused_table",
    "temp_migration_table"
  ],
  "_deprecated_columns": {
    "users": ["legacy_field", "unused_flag"],
    "orders": ["temp_status"]
  }
}
```

### Complex Transformations

```json
{
  "orders": {
    "status": {
      "targets": [
        {
          "db": "tenant",
          "table": "orders",
          "column": "status",
          "sql": "SELECT CASE WHEN status = 'COMPLETE' THEN 'fulfilled' WHEN status = 'PENDING' THEN 'processing' ELSE 'cancelled' END FROM orders"
        }
      ]
    }
  }
}
```

## GitHub Integration

### Setup

1. Create a GitHub repo for your migration:
```bash
gh repo create my-migration-project --public
cd my-migration-project
schema-migrator init
git add .
git commit -m "Initial migration project"
git push
```

2. Enable GitHub Issues:
   - Go to Settings → Features → Issues → Enable

3. Copy issue templates:
```bash
cp /path/to/schema-migrator/.github/ISSUE_TEMPLATE/* .github/ISSUE_TEMPLATE/
git add .github/
git commit -m "Add issue templates"
git push
```

### Using Issues for Schema Discussions

**Scenario 1: Question about a field**
1. Click "New Issue"
2. Choose "📋 Schema Question"
3. Fill in table/column details
4. Team discusses in comments
5. Update diagram based on decision

**Scenario 2: Suggest a migration change**
1. Click "New Issue"
2. Choose "💡 Migration Suggestion"
3. Describe current vs proposed mapping
4. Provide rationale
5. Review and implement

### Linking Issues to Columns

In the interactive diagram, click on a column → "Discuss on GitHub" → auto-opens issue with pre-filled table/column context.

## Customization

### Custom Categories

In your SQL comments, add category hints:

```sql
CREATE TABLE users (
    id INT PRIMARY KEY
) ENGINE=InnoDB COMMENT='Category: auth';
```

### Custom Colors

Edit the generated HTML's CSS:

```css
:root {
    --color-auth: #9b59b6;
    --color-jobs: #3498db;
    /* Add your own */
}
```

### Layout Persistence

Table positions are saved to browser localStorage automatically.

To reset:
```javascript
// In browser console
localStorage.removeItem('tablePositions');
location.reload();
```

## Advanced Features

### Multi-Database Support

Migrate to 3+ target databases:

```json
{
  "audit_log": {
    "action": {
      "targets": [
        {"db": "tenant", "table": "audit", "column": "action"},
        {"db": "central", "table": "audit_summary", "column": "action"},
        {"db": "analytics", "table": "events", "column": "event_type"}
      ]
    }
  }
}
```

### Conditional Migrations

```json
{
  "users": {
    "role": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "role",
          "sql": "SELECT role FROM users WHERE internal_user = 0"
        }
      ],
      "conditions": "Only migrate non-internal users"
    }
  }
}
```

### Validation

```bash
schema-migrator validate
```

Checks:
- All source columns have targets or are deprecated
- All SQL queries are syntactically valid
- No orphaned foreign keys
- Consistent field types

## Troubleshooting

### Issue: Diagram not showing

**Solution**: Check browser console for errors. Ensure `field_mappings.json` is valid JSON.

### Issue: Tables overlapping

**Solution**: Drag to reposition. Positions save automatically.

### Issue: Foreign keys missing

**Solution**: Ensure your SQL has `FOREIGN KEY` constraints defined.

### Issue: "Table not found" errors

**Solution**: Check that table names in `field_mappings.json` exactly match schema SQL.

## Best Practices

1. **Version Control Everything** - schemas, mappings, and generated diagrams
2. **Document Decisions** - Use GitHub Issues for discussions
3. **Incremental Migration** - Map tables one at a time
4. **Test Queries** - Validate SQL in `field_mappings.json`
5. **Review Regularly** - Update diagram as schema evolves

## Example Projects

See `examples/` directory for complete working examples:
- `ecommerce/` - Monolith → Multi-tenant e-commerce
- `saas/` - SaaS platform migration
- `healthcare/` - HIPAA-compliant medical records migration

## Support

- **GitHub Issues**: Report bugs or request features
- **Discussions**: Ask questions and share ideas
- **Documentation**: Full docs at `/docs`

---

Ready to start? Run `schema-migrator init` and begin your migration journey! 🚀


