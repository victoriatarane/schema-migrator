# Schema Migrator - Quick Start

## 🎯 What You Have

**Two Separate Projects:**

1. **`schema-migrator/`** - Your **PUBLIC** portfolio project
   - Generic, reusable Python package
   - Example schemas (e-commerce)
   - Ready for GitHub & PyPI

2. **`ctx-schema-migration/`** - Your **PRIVATE** internal project
   - Company-specific schemas
   - Uses the `schema-migrator` package
   - Stays confidential

## 🚀 Push to GitHub (3 Steps)

### Step 1: Review & Update Personal Info

```bash
cd /Users/victoriatarane/projects/dashboard-cortechs-ai/schema-migrator

# Update these files with your info:
# - README.md: Replace YOUR_USERNAME with your GitHub username
# - README.md: Replace your.email@example.com with your email
# - setup.py: Update author_email
```

### Step 2: Initialize Git & Push

```bash
cd /Users/victoriatarane/projects/dashboard-cortechs-ai/schema-migrator

# Initialize git
git init
git add .
git commit -m "Initial commit: Schema Migrator v1.0.0

Interactive database schema migration toolkit with visual lineage tracking.

Features:
- Drag-and-drop ER diagram with FK relationships
- Multi-target migration support
- Field lineage tracking
- GitHub Issues integration
- DICOM-compliant support
- Responsive design
- Zero database connection required
"

# Create GitHub repo (you'll need GitHub CLI or do this manually)
# gh repo create schema-migrator --public --source=. --remote=origin

# Or manually:
# 1. Go to https://github.com/new
# 2. Name: schema-migrator
# 3. Description: Interactive database schema migration toolkit
# 4. Public
# 5. Don't initialize with README (you already have one)
# 6. Create repository

# Then add remote and push:
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/schema-migrator.git
git push -u origin main
```

### Step 3: Add GitHub Pages (Optional)

Host the demo diagram on GitHub Pages:

```bash
# Create gh-pages branch
git checkout --orphan gh-pages

# Remove everything except examples
git rm -rf .
cp -r examples/ecommerce/* .
python -m schema_migrator.builder  # Generate demo diagram
git add tools/schema_diagram.html
mv tools/schema_diagram.html index.html
git add index.html
git commit -m "Add demo diagram"
git push origin gh-pages

# Switch back
git checkout main

# Enable GitHub Pages:
# Go to Settings → Pages → Source: gh-pages branch
# Your demo will be at: https://YOUR_USERNAME.github.io/schema-migrator/
```

## ✅ Checklist Before Pushing

- [ ] No company-specific data in `schemas/` (only examples)
- [ ] No database credentials anywhere
- [ ] Personal contact info updated (not company)
- [ ] README has your GitHub username
- [ ] LICENSE has your name and year
- [ ] No internal business logic exposed

## 🔒 Keep Internal Project Private

Your `ctx-schema-migration/` directory is **separate** and contains proprietary data:

```bash
cd /Users/victoriatarane/projects/dashboard-cortechs-ai/ctx-schema-migration

# Option 1: Private GitHub repo (in your organization)
git init
git add .
git commit -m "Internal migration project"
# gh repo create healthlytix/ctx-schema-migration --private

# Option 2: Just keep it local (no git)
# Back up regularly to secure location
```

## 📖 Portfolio Presentation

### For Your README.md Portfolio Section

```markdown
### Schema Migrator

**Problem**: Complex database migrations require careful planning and team alignment.

**Solution**: Built an interactive schema migration toolkit that visualizes relationships, tracks field lineage, and enables GitHub-based discussions.

**Tech Stack**: Python, JavaScript (vanilla), SVG, SQL parsing

**Key Features**:
- Interactive drag-and-drop ER diagrams
- Multi-target database support
- GitHub Issues integration for collaboration
- Zero-config static HTML generation

**Results**: Open-sourced for community use

[Live Demo](https://YOUR_USERNAME.github.io/schema-migrator) | [Source Code](https://github.com/YOUR_USERNAME/schema-migrator)
```

### For Resume/LinkedIn

**Schema Migrator** (2024)
- Developed open-source Python package for database schema migrations
- Interactive visualization with 200+ tables, 1000+ field mappings
- Implemented multi-target migration algorithm supporting 3+ destination databases
- Integrated GitHub Issues API for collaborative schema review workflow
- Technologies: Python, JavaScript, SQL parsing, SVG rendering

## 🎓 Next Steps

### After Pushing to GitHub

1. **Add Topics** (on GitHub repo page):
   - `database-migration`
   - `schema-visualization`
   - `data-engineering`
   - `python`
   - `interactive-diagram`

2. **Create Release**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Then create release on GitHub with release notes

3. **Share**:
   - LinkedIn post with demo GIF
   - Dev.to article: "Building an Interactive Schema Migration Tool"
   - Reddit: r/datascience, r/Python

4. **Publish to PyPI** (when ready):
   ```bash
   pip install build twine
   python -m build
   python -m twine upload dist/*
   ```

## 🐛 Troubleshooting

**Q: Can I use this with my current internal project?**
A: Yes! The internal project already uses this package:

```bash
cd /Users/victoriatarane/projects/dashboard-cortechs-ai/ctx-schema-migration
pip install -e ../schema-migrator
python scripts/build_diagram.py  # Uses the package!
```

**Q: What if I want to update the package later?**
A: Make changes in `schema-migrator/`, then reinstall in internal project:

```bash
cd schema-migrator
git commit -m "feat: Add new feature"
git push

cd ../ctx-schema-migration
pip install -e ../schema-migrator --force-reinstall
```

**Q: Is my company data safe?**
A: Yes! The two directories are completely separate:
- `schema-migrator/` = public package (generic examples)
- `ctx-schema-migration/` = private data (stays local)

## 📞 Questions?

Read the full guide: `docs/DUAL_REPO_SETUP.md`

---

**Ready?** Run the commands in Step 2 above! 🚀


