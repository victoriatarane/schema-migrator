# Configuration Reference

## Project Structure

Schema Migrator expects the following directory structure:

```
your-project/
├── schemas/
│   ├── old/
│   │   └── schema.sql          # Required: Legacy schema
│   └── new/
│       ├── tenant_schema.sql   # Required: New tenant schema
│       └── central_schema.sql  # Optional: Central registry schema
├── scripts/
│   └── field_mappings.json     # Required: Field migration mappings
└── tools/
    └── schema_diagram.html     # Generated output
```

## Creating the Structure

```bash
# Option 1: Use the CLI
schema-migrator init

# Option 2: Manual creation
mkdir -p schemas/old schemas/new scripts tools docs
```

## SQL Schema Files

### Old Schema (`schemas/old/schema.sql`)

Your legacy database schema. Export using:

```bash
# MySQL
mysqldump -u username -p --no-data database_name > schemas/old/schema.sql

# PostgreSQL
pg_dump -U username --schema-only database_name > schemas/old/schema.sql
```

**Format Requirements**:
- Standard SQL `CREATE TABLE` statements
- Include `FOREIGN KEY` constraints for relationship arrows
- Comments are optional but helpful

**Example**:
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100),
    email VARCHAR(255),
    created_at DATETIME
) ENGINE=InnoDB COMMENT='User accounts';
```

### New Tenant Schema (`schemas/new/tenant_schema.sql`)

Your new per-tenant database schema.

**Source Attribution**:
Use `COMMENT` to indicate source:

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) COMMENT 'Source: users.username',
    email VARCHAR(255) COMMENT 'Source: users.email',
    created_at DATETIME COMMENT 'Source: users.created_at'
) ENGINE=InnoDB;
```

The diagram will automatically parse these comments to show field lineage.

### Central Schema (`schemas/new/central_schema.sql`)

Optional. Use for cross-tenant analytics or central registry.

```sql
CREATE TABLE sites_registry (
    id INT PRIMARY KEY AUTO_INCREMENT,
    site_uuid CHAR(36) UNIQUE,
    site_name VARCHAR(128) COMMENT 'Source: users.username',
    created_at DATETIME COMMENT 'Source: users.created_at'
) ENGINE=InnoDB;
```

## Field Mappings File

### Location

`scripts/field_mappings.json`

### Format

```json
{
  "_meta": {
    "version": "2.0.0",
    "description": "Your migration description",
    "source": "Legacy database name",
    "targets": ["Target database names"]
  },
  "source_table": {
    "source_column": {
      "targets": [
        {
          "db": "tenant",
          "table": "target_table",
          "column": "target_column",
          "sql": "SELECT source_column FROM source_table WHERE condition"
        }
      ]
    }
  },
  "_deprecated_tables": ["old_unused_table"],
  "_deprecated_columns": {
    "table_name": ["column1", "column2"]
  }
}
```

### Fields

#### `_meta` (optional)
Metadata about your migration:
- `version`: Mapping file version (use "2.0.0")
- `description`: Brief description
- `source`: Source database name
- `targets`: List of target database names

#### Table Mappings
Key = source table name, value = column mappings

#### Column Mappings
Key = source column name, value = target configuration

#### Target Configuration
- `db`: Target database (`"tenant"` or `"central"`)
- `table`: Target table name
- `column`: Target column name
- `sql`: Migration SQL query (optional, for documentation)

#### `_deprecated_tables` (optional)
Array of table names that won't be migrated

#### `_deprecated_columns` (optional)
Object mapping table names to arrays of deprecated column names

### Examples

#### Simple One-to-One Mapping

```json
{
  "users": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email",
          "sql": "SELECT email FROM users"
        }
      ]
    }
  }
}
```

#### Multi-Target Mapping

One source field → multiple destinations:

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

#### With Transformations

```json
{
  "orders": {
    "status": {
      "targets": [
        {
          "db": "tenant",
          "table": "orders",
          "column": "status",
          "sql": "SELECT CASE WHEN status='COMPLETE' THEN 'fulfilled' ELSE 'processing' END FROM orders"
        }
      ]
    }
  }
}
```

#### Deprecated Fields

```json
{
  "_deprecated_tables": [
    "temp_table",
    "old_cache"
  ],
  "_deprecated_columns": {
    "users": ["legacy_field", "unused_flag"],
    "orders": ["temp_status"]
  }
}
```

## CLI Configuration

### Command-Line Options

```bash
schema-migrator build \
  --schemas-dir schemas \
  --mappings scripts/field_mappings.json \
  --output tools/schema_diagram.html \
  --github-repo victoriatarane/my-migration-project
```

### Options Reference

| Option | Description | Default |
|--------|-------------|---------|
| `--schemas-dir` | Directory containing schema folders | `schemas/` |
| `--mappings` | Path to field mappings JSON | `scripts/field_mappings.json` |
| `--output` | Output HTML file path | `tools/schema_diagram.html` |
| `--github-repo` | GitHub repo for issues (owner/repo) | None |

## GitHub Integration

### Setup

1. Create `github_config.json` (optional):

```json
{
  "repo_owner": "victoriatarane",
  "repo_name": "my-migration-project",
  "enable_comments": true,
  "issue_labels": ["schema-question", "needs-review"]
}
```

2. Use `--github-repo` flag:

```bash
schema-migrator build --github-repo victoriatarane/my-migration-project
```

### Issue Templates

Copy templates from schema-migrator repo:

```bash
cp -r node_modules/schema-migrator/.github/ISSUE_TEMPLATE .github/
```

Or download from: [GitHub Templates](https://github.com/victoriatarane/schema-migrator/tree/main/.github/ISSUE_TEMPLATE)

## Environment Variables

### Optional Configuration

```bash
# Default schemas directory
export SCHEMA_MIGRATOR_SCHEMAS_DIR=/path/to/schemas

# Default mappings file
export SCHEMA_MIGRATOR_MAPPINGS=/path/to/mappings.json

# Default output directory
export SCHEMA_MIGRATOR_OUTPUT=/path/to/output
```

### Using .env File

Create `.env` in project root:

```bash
SCHEMA_MIGRATOR_SCHEMAS_DIR=schemas
SCHEMA_MIGRATOR_MAPPINGS=scripts/field_mappings.json
SCHEMA_MIGRATOR_OUTPUT=tools/schema_diagram.html
GITHUB_REPO=victoriatarane/my-migration-project
```

## Output Configuration

### HTML Output

The generated `schema_diagram.html` is self-contained:
- All data embedded (no external dependencies)
- Uses localStorage for saving table positions
- Fully interactive (drag, click, navigate)

### Customization

Edit the generated HTML to customize:

**Colors** (CSS variables):
```css
:root {
    --color-core: #e74c3c;
    --color-auth: #9b59b6;
    --color-jobs: #3498db;
    /* Add your own */
}
```

**Layout** (JavaScript):
```javascript
// In the generated HTML, find:
const spiralYOffset = 300;  // Adjust spiral position
const hGap = 25;            // Horizontal spacing
const vGap = 25;            // Vertical spacing
```

## Best Practices

### 1. Version Control

```bash
git add schemas/ scripts/field_mappings.json
git commit -m "Update schema mappings"

# Don't commit generated HTML (changes frequently)
echo "tools/*.html" >> .gitignore
```

### 2. Validation

Validate your configuration before building:

```bash
schema-migrator validate
```

### 3. Incremental Development

Build frequently during development:

```bash
# Watch for changes (requires entr)
ls schemas/**/*.sql scripts/field_mappings.json | entr schema-migrator build
```

### 4. Documentation

Add a `README.md` in your schemas directory:

```markdown
# Database Schemas

## Old Schema
Production database as of 2024-01-15
Exported from: production-db.example.com

## New Schema
Multi-tenant architecture design
Target deployment: Q2 2024
```

## Troubleshooting

### Issue: Tables not appearing in diagram

**Check**:
1. SQL syntax is valid
2. Table names match exactly in mappings file
3. No typos in CREATE TABLE statements

### Issue: Foreign keys not showing

**Solution**: Ensure FOREIGN KEY constraints are in your SQL:

```sql
FOREIGN KEY (user_id) REFERENCES users(id)
```

### Issue: Field lineage not showing

**Solution**: Add COMMENT with source information:

```sql
column_name VARCHAR(100) COMMENT 'Source: old_table.old_column'
```

## Advanced Configuration

### Custom Categories

Add category to table comments:

```sql
CREATE TABLE users (
    ...
) ENGINE=InnoDB COMMENT='Category: auth';
```

Supported categories:
- `core`, `auth`, `config`, `imaging`, `jobs`, `logging`, `metrics`, `lookup`, `legacy`, `central`

### Multiple Source Databases

Not yet supported. Workaround: merge schemas into one file with table name prefixes.

---

**Next**: [Field Mapping Syntax](FIELD_MAPPINGS.md)

