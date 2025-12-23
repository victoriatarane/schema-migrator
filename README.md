# Schema Migrator

**Interactive Database Schema Migration Toolkit with Visual Lineage Tracking**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Features

- **Interactive Schema Visualization** - Drag-and-drop ER diagram with FK relationships
- **Multi-Target Migration** - Migrate one source field to multiple destination databases
- **Field Lineage Tracking** - Click any column to see its source/destination across schemas
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

## 📊 Example Use Case

**Problem**: Legacy monolithic database → Multi-tenant architecture

**Solution**:
1. Define old schema (1 database, 50 tables)
2. Define new schemas (per-tenant DB + central registry)
3. Map fields with migration SQL
4. Generate interactive diagram
5. Share with team via GitHub Pages
6. Discuss changes via GitHub Issues

## 🎨 Screenshot

![Schema Diagram Example](docs/images/screenshot.png)

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

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [Field Mapping Syntax](docs/FIELD_MAPPINGS.md)
- [GitHub Integration](docs/GITHUB_INTEGRATION.md)
- [Contributing](CONTRIBUTING.md)

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

