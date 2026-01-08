"""
Schema Migrator - Interactive Database Schema Migration Toolkit
"""
from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="schema-migrator",
    version="1.3.4",
    author="Victoria Tarane",
    author_email="victoriatarane@gmail.com",
    description="Interactive database schema migration toolkit with visual lineage tracking and JSON-driven execution",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/victoriatarane/schema-migrator",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "schema-migrator=schema_migrator.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "schema_migrator": [
            "templates/*.html",
            "templates/*.css",
            "templates/*.js",
        ],
    },
    zip_safe=False,
)

