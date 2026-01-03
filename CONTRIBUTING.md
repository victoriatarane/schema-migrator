# Contributing to Schema Migrator

Thank you for your interest in contributing! 🎉

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/victoriatarane/schema-migrator.git
cd schema-migrator
```

### 2. Install Development Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
```

### 3. Make Your Changes

- Create a new branch: `git checkout -b feature/your-feature-name`
- Make your changes
- Add tests if applicable
- Update documentation

### 4. Test Your Changes

```bash
# Run tests
pytest

# Check code style
black src/ tests/
flake8 src/ tests/

# Test the CLI
schema-migrator init
schema-migrator build
```

### 5. Submit a Pull Request

- Push your branch: `git push origin feature/your-feature-name`
- Open a PR on GitHub
- Describe your changes clearly
- Link any related issues

## Development Guidelines

### Code Style

- Follow PEP 8
- Use `black` for formatting
- Use type hints where appropriate
- Write docstrings for public functions

### Commit Messages

Use conventional commits:

```
feat: Add GitHub Issues integration
fix: Resolve arrow overlap issue
docs: Update installation guide
test: Add tests for field mapping parser
```

### Testing

- Write tests for new features
- Ensure existing tests pass
- Aim for >80% code coverage

### Documentation

- Update README.md for user-facing changes
- Add docstrings for new functions
- Create examples for new features

## Project Structure

```
schema-migrator/
├── src/schema_migrator/
│   ├── __init__.py
│   ├── cli.py           # Command-line interface
│   ├── builder.py       # Main diagram builder
│   ├── examples.py      # Example schemas
│   └── templates/       # HTML/CSS/JS templates
├── tests/               # Unit tests
├── docs/                # Documentation
├── examples/            # Example projects
└── setup.py
```

## Feature Requests

Have an idea? Open an issue with:

- Clear description of the feature
- Use case / motivation
- Example of how it would work

## Bug Reports

Found a bug? Open an issue with:

- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

## Questions?

- Open a GitHub Discussion
- Check existing issues/PRs
- Read the documentation

Thank you for contributing! 🙏


