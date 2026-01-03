# Installation Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (for cloning from source)

## Quick Install (PyPI)

> **Note**: Package will be published to PyPI soon. For now, install from source.

```bash
pip install schema-migrator
```

## Install from Source

### 1. Clone the Repository

```bash
git clone https://github.com/victoriatarane/schema-migrator.git
cd schema-migrator
```

### 2. Install in Development Mode

This allows you to edit the code and see changes immediately:

```bash
pip install -e .
```

### 3. Verify Installation

```bash
schema-migrator --version
```

Expected output:
```
schema-migrator 1.0.0
```

## Optional Dependencies

### For GitHub Integration

```bash
pip install PyGithub
```

This enables the GitHub Issues integration feature.

### For Development

```bash
pip install -e .[dev]
```

This installs additional development tools:
- pytest (testing)
- pytest-cov (code coverage)
- black (code formatting)
- flake8 (linting)

## Virtual Environment (Recommended)

### Using venv

```bash
# Create virtual environment
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install schema-migrator
pip install -e .
```

### Using conda

```bash
# Create conda environment
conda create -n schema-migrator python=3.10

# Activate
conda activate schema-migrator

# Install
pip install -e .
```

## Platform-Specific Notes

### macOS

No special requirements. Use the standard installation.

### Linux

You may need to install development headers:

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev

# Fedora/RHEL
sudo dnf install python3-devel
```

### Windows

Install via pip. If you encounter issues with PyMySQL or cryptography:

```bash
pip install --upgrade pip setuptools wheel
pip install -e .
```

## Troubleshooting

### Issue: `command not found: schema-migrator`

**Solution**: Ensure pip's bin directory is in your PATH:

```bash
# macOS/Linux
export PATH="$HOME/.local/bin:$PATH"

# Or find pip's bin directory
python3 -m pip show schema-migrator
```

### Issue: `ModuleNotFoundError: No module named 'schema_migrator'`

**Solution**: Reinstall in development mode:

```bash
pip uninstall schema-migrator
pip install -e .
```

### Issue: Permission denied during installation

**Solution**: Use `--user` flag or virtual environment:

```bash
pip install --user -e .
```

### Issue: SSL certificate errors when installing dependencies

**Solution**: Update certifi:

```bash
pip install --upgrade certifi
```

## Updating

### From PyPI

```bash
pip install --upgrade schema-migrator
```

### From Source

```bash
cd schema-migrator
git pull origin main
pip install -e . --force-reinstall
```

## Uninstalling

```bash
pip uninstall schema-migrator
```

## Next Steps

After installation:

1. **Initialize a new project**: `schema-migrator init`
2. **Read the usage guide**: [USAGE_GUIDE.md](USAGE_GUIDE.md)
3. **Try the live demo**: [https://victoriatarane.github.io/schema-migrator/](https://victoriatarane.github.io/schema-migrator/)

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/victoriatarane/schema-migrator/issues)
- **Documentation**: [Full Docs](USAGE_GUIDE.md)
- **Examples**: See `examples/` directory in the repo

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8 | 3.10+ |
| RAM | 512 MB | 1 GB+ |
| Disk Space | 50 MB | 100 MB |
| OS | Any | macOS, Linux, Windows 10+ |

---

**Installation successful?** → Continue to [Configuration Reference](CONFIGURATION.md)


