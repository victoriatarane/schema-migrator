# GitHub Integration

Collaborate on schema migrations using GitHub Issues directly from the interactive diagram.

## Overview

Schema Migrator integrates with GitHub Issues to enable:
- 💬 **Discussions** on specific tables/columns
- 📝 **Change proposals** with structured templates
- 🔍 **Traceability** of migration decisions
- 👥 **Team collaboration** on schema design

## Setup

### 1. Enable GitHub Issues

Ensure Issues are enabled in your repository:

1. Go to your GitHub repo → **Settings**
2. Scroll to **Features**
3. Check **Issues**

### 2. Add Issue Templates

Copy the issue templates to your repository:

```bash
cd your-migration-project

# Create templates directory
mkdir -p .github/ISSUE_TEMPLATE

# Copy from schema-migrator repo
cp node_modules/schema-migrator/.github/ISSUE_TEMPLATE/* .github/ISSUE_TEMPLATE/
```

Or download manually:
- [schema_question.yml](https://github.com/victoriatarane/schema-migrator/blob/main/.github/ISSUE_TEMPLATE/schema_question.yml)
- [migration_suggestion.yml](https://github.com/victoriatarane/schema-migrator/blob/main/.github/ISSUE_TEMPLATE/migration_suggestion.yml)

### 3. Configure Repository

Build diagram with GitHub repo specified:

```bash
schema-migrator build --github-repo YOUR_USERNAME/your-migration-project
```

Or add to your build script:

```python
from schema_migrator import build_diagram

build_diagram(
    old_schema="schemas/old/schema.sql",
    tenant_schema="schemas/new/tenant_schema.sql",
    central_schema="schemas/new/central_schema.sql",
    mappings="scripts/field_mappings.json",
    output="tools/schema_diagram.html",
    github_repo="YOUR_USERNAME/your-migration-project"  # Add this
)
```

## Issue Templates

### 📋 Schema Question

Ask questions about specific tables or columns.

**Use cases**:
- "Why is this field deprecated?"
- "Should this be in tenant or central DB?"
- "What's the expected data format?"

**Template includes**:
- Schema type (Old/New Tenant/Central)
- Table name
- Column name (optional)
- Question
- Additional context

**Example**:
```
Title: [SCHEMA] Why is users.legacy_password deprecated?

Schema Type: Old Schema
Table: users
Column: legacy_password

Question: Why is this field being deprecated? Do we need to migrate 
historical password data?

Context: This field appears to have data for 50% of users.
```

### 💡 Migration Suggestion

Propose changes to field mappings.

**Use cases**:
- Suggest different target database
- Propose transformation logic
- Flag compliance/security concerns

**Template includes**:
- Old schema table/column
- Current migration status
- Suggested target
- Rationale
- Impact assessment
- SQL suggestion (optional)

**Example**:
```
Title: [SUGGESTION] Move users.email to central DB

Old Table: users
Old Column: email
Current Status: Migrated to Tenant DB
Suggested Target: Central DB Only

Rationale: For compliance, email should be stored in central DB with 
hashed values in tenant DBs. This allows for GDPR deletion requests 
across all tenants.

Impact: Would require updating authentication logic in tenant DBs to 
reference central email hash.

SQL: SELECT SHA2(email, 256) FROM users
```

## Workflow

### 1. Review Schema in Diagram

Open the interactive diagram:

```bash
open tools/schema_diagram.html
```

### 2. Click on Table/Column

Navigate to the table or column you have questions about.

### 3. Open Discussion

The diagram will show a "Discuss on GitHub" link (when GitHub integration is enabled).

Clicking opens GitHub with pre-filled context:
- Table name
- Column name
- Current schema
- Migration status

### 4. Create Issue

Use one of the templates:
- 📋 **Schema Question** - for clarifications
- 💡 **Migration Suggestion** - for proposing changes

### 5. Team Discussion

Team members comment on the issue with:
- Answers
- Concerns
- Alternative suggestions
- Implementation details

### 6. Update Mappings

After decision, update `field_mappings.json`:

```json
{
  "users": {
    "email": {
      "targets": [{
        "db": "central",  // Updated based on issue discussion
        "table": "user_registry",
        "column": "email",
        "sql": "SELECT email FROM users",
        "notes": "Decision made in issue #42"
      }]
    }
  }
}
```

### 7. Regenerate Diagram

```bash
schema-migrator build
```

### 8. Close Issue

Once implemented, close the issue with a comment:

```
Implemented in commit abc1234. Field now migrates to central DB.
```

## Labels

Organize issues with labels:

### Default Labels

- `schema-question` - Questions about schema design
- `needs-review` - Awaiting team review
- `migration-suggestion` - Proposed changes
- `approved` - Approved for implementation
- `implemented` - Already implemented

### Custom Labels

Add your own:

```
- high-priority
- security-concern
- compliance
- breaking-change
- discussion
```

## Best Practices

### 1. Be Specific

**Good**:
> "Should `users.email` be in tenant DB or central DB? Concern: GDPR compliance for cross-tenant user lookup."

**Bad**:
> "What about emails?"

### 2. Reference Context

Include:
- Current usage in codebase
- Data volume/sensitivity
- Related tables/fields
- Compliance requirements

### 3. Use Cross-References

Link related issues:

```
Related to #23 (PII handling strategy)
Blocks #45 (Authentication refactor)
```

### 4. Document Decisions

Add outcomes to:
- Issue comments
- `field_mappings.json` notes
- Project README
- Decision log (ADR)

### 5. Regular Review

Hold weekly review sessions:
1. Triage new issues
2. Discuss open questions
3. Make decisions
4. Assign implementation

## Advanced Usage

### API Integration

Use GitHub API to automate:

```python
from github import Github

g = Github("your_token")
repo = g.get_repo("YOUR_USERNAME/your-migration-project")

# Create issue programmatically
repo.create_issue(
    title="[SCHEMA] Question about orders.status",
    body="Should this use enum or string?",
    labels=["schema-question", "needs-review"]
)
```

### Automated Notifications

Set up notifications:
1. Go to repo → **Watch** → **Custom**
2. Check **Issues**
3. Get notified of all schema discussions

### Project Board

Track migration progress:

1. Create **Project** in GitHub
2. Add columns:
   - **Questions** (schema-question issues)
   - **In Review** (needs-review)
   - **Approved** (approved)
   - **Implemented** (closed)
3. Auto-add issues to project
4. Move cards as status changes

### Milestones

Group issues by migration phase:

```
- Phase 1: Core Tables (users, accounts)
- Phase 2: Business Logic (orders, products)
- Phase 3: Analytics (reporting, metrics)
```

Assign issues to milestones for tracking.

## Troubleshooting

### Issue: "Discuss on GitHub" link not appearing

**Solution**: Ensure you built diagram with `--github-repo` flag:

```bash
schema-migrator build --github-repo YOUR_USERNAME/your-repo
```

### Issue: Template not showing

**Solution**: Check templates are in correct location:

```bash
ls .github/ISSUE_TEMPLATE/
# Should show:
# migration_suggestion.yml
# schema_question.yml
```

### Issue: Can't create issues

**Solution**: Check repository permissions:
- Ensure Issues are enabled (Settings → Features)
- Ensure you have write access to repository

## Example Workflow

### Scenario: Email Field Migration

**1. Initial Mapping**:
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

**2. Security Review**:
Alice opens issue:
> [SCHEMA] Should users.email be in central DB?
> 
> For GDPR compliance, we may need to delete user emails across all tenants.
> Currently each tenant has its own copy, making this difficult.

**3. Team Discussion**:
- Bob: "Good point, but authentication needs email. How do we handle that?"
- Carol: "We could store hashed email in tenant DB, actual email in central."
- David: "Agreed. I'll implement a lookup service."

**4. Decision**:
Approved by team. Update mappings:

```json
{
  "users": {
    "email": {
      "targets": [
        {
          "db": "tenant",
          "table": "users",
          "column": "email_hash",
          "sql": "SELECT SHA2(email, 256) FROM users"
        },
        {
          "db": "central",
          "table": "user_registry",
          "column": "email",
          "sql": "SELECT email FROM users",
          "notes": "Decision from issue #42"
        }
      ]
    }
  }
}
```

**5. Implementation**:
- Code changes committed
- Diagram regenerated
- Issue closed: "Implemented in PR #123"

**6. Documentation**:
Added to ADR (Architecture Decision Record):
```markdown
## ADR-005: Store emails in central DB

**Status**: Accepted
**Context**: GDPR compliance for cross-tenant user management
**Decision**: Store actual emails in central DB, hashed in tenant DBs
**Consequences**: Requires lookup service for authentication
**References**: GitHub issue #42
```

## Resources

- [GitHub Issues Documentation](https://docs.github.com/en/issues)
- [Creating Issue Templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [GitHub API](https://docs.github.com/en/rest/issues)

---

**Next Steps**: Start collaborating! Open your first issue and get team feedback on your migration strategy.


