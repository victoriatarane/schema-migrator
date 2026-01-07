# Schema Migrator

**Interactive Database Schema Migration Toolkit with Visual Lineage Tracking**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/victoriatarane/schema-migrator.svg)](https://github.com/victoriatarane/schema-migrator/stargazers)
[![Live Demo](https://img.shields.io/badge/demo-live-success.svg)](https://victoriatarane.github.io/schema-migrator/)

## 🚀 Features

- **Interactive Schema Visualization** - Drag-and-drop ER diagram with FK relationships
- **JSON-Driven Execution** ⭐ NEW - Execute migrations directly from field_mappings.json
- **Multi-Target Migration** - Migrate one source field to multiple destination databases
- **Dual-Database Support** - Separate tenant and central databases
- **Field Lineage Tracking** - Click any column to see its source/destination across schemas
- **Single Source of Truth** - JSON config drives both diagram AND execution
- **GitHub Issues Integration** - Comment and discuss schema changes directly in the diagram
- **Responsive Design** - Works on any screen size with adaptive layouts
- **Zero Database Connection** - Static HTML generation from SQL schema files

## 📦 Installation

```bash
pip install schema-migrator
```

Or install from source:

```bash
git clone https://github.com/victoriatarane/schema-migrator.git
cd schema-migrator
pip install -e .
```

## 🎯 Quick Start

### 1. Prepare Your Schemas

Create three SQL schema files:
- `schemas/old/schema.sql` - Your current/legacy schema
- `schemas/new/tenant_schema.sql` - Your new schema
- `schemas/new/central_schema.sql` - Optional: central/summary database

### 2. Define Field Mappings

Create `scripts/field_mappings.json`:

```json
{
  "_meta": {
    "version": "2.0.0",
    "description": "Field migration mappings"
  },
  "users": {
    "username": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "username",
          "sql": "SELECT username FROM old_users WHERE active = 1"
        }
      ]
    }
  }
}
```

### 3. Generate Interactive Diagram

```bash
schema-migrator build
```

This creates `tools/schema_diagram.html` - open it in any browser!

### 4. Execute Migration (Production-Ready in v1.3.0!)

```python
import pymysql
from schema_migrator import MigrationExecutor

# Connect to database
conn = pymysql.connect(host='localhost', user='root', password='pass', 
                       cursorclass=pymysql.cursors.DictCursor)

# Initialize executor
executor = MigrationExecutor(
    mappings_file='scripts/field_mappings.json',
    source_conn=conn,
    source_db='legacy_db'
)

# Migrate a table
stats = executor.migrate_table(
    old_table='users',
    target_db='app_tenant_abc',
    target_db_type='tenant',
    filters={'is_active': 1, 'tenant_id': 123}
)

print(f"✓ Migrated: {stats['migrated']} rows")
```

## 🎯 Live Demo

**👉 [Try the Interactive Demo](https://victoriatarane.github.io/schema-migrator/)**

Experience the full functionality:
- Drag tables to reposition
- Click tables to view columns and migration details
- Hover over FK arrows to see relationship details
- Toggle between Old Schema, New Tenant, and Central DB views
- Click columns to navigate between schemas

## 📊 Example Use Case

**Problem**: Legacy monolithic database → Multi-tenant architecture

**Solution**:
1. Define old schema (1 database, 50 tables)
2. Define new schemas (per-tenant DB + central registry)
3. Map fields with migration SQL
4. Generate interactive diagram
5. Share with team via GitHub Pages
6. Discuss changes via GitHub Issues

## 🎨 Features in Action

## 🔧 Advanced Usage

### Multi-Target Migrations

Migrate one field to multiple destinations:

```json
{
  "old_table": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email",
          "sql": "SELECT email FROM old_users"
        },
        {
          "db": "central",
          "table": "user_registry",
          "column": "email_hash",
          "sql": "SELECT SHA2(email, 256) FROM old_users"
        }
      ]
    }
  }
}
```

### GitHub Issues Integration

Enable collaborative schema reviews:

1. Create GitHub repo for your migration project
2. Enable Issues in repo settings
3. Add `github_config.json`:

```json
{
  "repo_owner": "YOUR_USERNAME",
  "repo_name": "your-migration-project",
  "enable_comments": true
}
```

4. Users can now comment on tables/columns with auto-linked GitHub Issues

### Custom Layouts

Save your preferred table positions:
- **Drag** any table to reposition
- **Click** to select and view columns
- Positions auto-save to browser localStorage

### Export Options

```bash
# Generate diagram
schema-migrator build

# Generate + run migration script
schema-migrator build --with-migration

# Validate mappings only
schema-migrator validate
```

## 💡 Why Use This Tool?

### Single Source of Truth (v1.2.0+)

**Problem:** Separate documentation and execution can drift apart
- `field_mappings.json` → Diagram (what stakeholders see)
- `migrate_script.py` → Execution (what actually runs)
- ❌ Risk: They get out of sync!

**Solution:** JSON drives BOTH diagram and execution
- ✅ Diagram reads JSON → Visual documentation
- ✅ Executor reads JSON → Actual migration
- ✅ **Impossible to drift!**

### Competitive Advantage

| Feature | Liquibase | Flyway | dbt | This Tool |
|---------|:---------:|:------:|:---:|:---------:|
| Schema versioning | ✅ | ✅ | ❌ | ⚠️ |
| Data migration | ❌ | ❌ | ✅ | ✅ |
| Complex transformations | ⚠️ | ⚠️ | ✅ | ✅ |
| Multi-target fields | ❌ | ❌ | ❌ | 🏆 |
| Interactive visualization | ❌ | ❌ | ⚠️ | 🏆 |
| JSON config | ❌ | ❌ | ⚠️ | ✅ |
| Single source of truth | ✅ | ✅ | ✅ | 🏆 |

**Best for:** Complex schema refactoring, multi-tenant migrations, incremental rollouts

## 📚 Documentation

- [Usage Guide](docs/USAGE_GUIDE.md)
- [Contributing](CONTRIBUTING.md)
- [Quick Start](QUICK_START.md)

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📝 License

MIT License - see [LICENSE](LICENSE)

## 🙏 Acknowledgments

Built with:
- Python 3.8+
- Pure JavaScript (no frameworks!)
- SVG for diagram rendering

## 📧 Contact

**Victoria Tarane**
- GitHub: [@victoriatarane](https://github.com/victoriatarane)
- LinkedIn: [Your Profile](https://www.linkedin.com/in/victoria-tarane-54a86b5b/)

---

⭐ If this project helped you, please give it a star!

