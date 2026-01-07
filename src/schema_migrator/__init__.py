"""
Schema Migrator - Interactive Database Schema Migration Toolkit

Provides:
1. Diagram Generation: Visual HTML diagrams of schema relationships
2. Migration Execution: Run migrations from field_mappings.json (v1.2.0+)
"""

__version__ = "1.3.3"
__author__ = "Victoria Tarane"

from .builder import build_diagram
from .executor import MigrationExecutor

__all__ = ["build_diagram", "MigrationExecutor"]


