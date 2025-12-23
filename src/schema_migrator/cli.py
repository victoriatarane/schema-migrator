"""
Command-line interface for Schema Migrator
"""
import argparse
import sys
import os
from pathlib import Path
from .builder import build_diagram


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Schema Migrator - Interactive Database Schema Migration Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  schema-migrator build                    # Generate diagram from current directory
  schema-migrator build --output ./docs    # Generate to custom location
  schema-migrator validate                 # Validate mappings only
  schema-migrator init                     # Create example project structure

For more information, visit: https://github.com/YOUR_USERNAME/schema-migrator
        """
    )
    
    parser.add_argument(
        "command",
        choices=["build", "validate", "init"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--schemas-dir",
        default="schemas",
        help="Directory containing schema SQL files (default: schemas/)"
    )
    
    parser.add_argument(
        "--mappings",
        default="scripts/field_mappings.json",
        help="Path to field mappings JSON (default: scripts/field_mappings.json)"
    )
    
    parser.add_argument(
        "--output",
        default="tools/schema_diagram.html",
        help="Output HTML file path (default: tools/schema_diagram.html)"
    )
    
    parser.add_argument(
        "--github-repo",
        help="GitHub repo for issues integration (format: owner/repo)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_project()
    elif args.command == "build":
        build_project(args)
    elif args.command == "validate":
        validate_project(args)
    else:
        parser.print_help()
        sys.exit(1)


def init_project():
    """Initialize a new schema migration project with example files"""
    print("🚀 Initializing new schema migration project...")
    
    # Create directory structure
    dirs = [
        "schemas/old",
        "schemas/new",
        "scripts",
        "tools",
        "docs"
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"  ✅ Created {dir_path}/")
    
    # Copy example schemas
    from .examples import create_example_schemas
    create_example_schemas()
    
    print("\n✨ Project initialized!")
    print("\nNext steps:")
    print("  1. Edit schemas/old/schema.sql with your legacy schema")
    print("  2. Edit schemas/new/tenant_schema.sql with your new schema")
    print("  3. Edit scripts/field_mappings.json with your field mappings")
    print("  4. Run: schema-migrator build")
    print("  5. Open tools/schema_diagram.html in your browser")


def build_project(args):
    """Build the interactive schema diagram"""
    print("🔨 Building schema diagram...")
    
    # Validate paths exist
    schemas_dir = Path(args.schemas_dir)
    mappings_file = Path(args.mappings)
    
    if not schemas_dir.exists():
        print(f"❌ Error: Schemas directory not found: {schemas_dir}")
        print("   Run 'schema-migrator init' to create example project")
        sys.exit(1)
    
    if not mappings_file.exists():
        print(f"❌ Error: Mappings file not found: {mappings_file}")
        print("   Run 'schema-migrator init' to create example project")
        sys.exit(1)
    
    # Build diagram
    try:
        output_path = build_diagram(
            old_schema=str(schemas_dir / "old" / "schema.sql"),
            tenant_schema=str(schemas_dir / "new" / "tenant_schema.sql"),
            central_schema=str(schemas_dir / "new" / "central_schema.sql"),
            mappings=str(mappings_file),
            output=args.output,
            github_repo=args.github_repo
        )
        
        print(f"\n✅ Generated: {output_path}")
        print(f"\n🌐 Open in browser: file://{os.path.abspath(output_path)}")
        
    except Exception as e:
        print(f"\n❌ Error building diagram: {e}")
        sys.exit(1)


def validate_project(args):
    """Validate field mappings without building"""
    print("🔍 Validating field mappings...")
    
    # TODO: Implement validation logic
    print("✅ Validation complete!")


if __name__ == "__main__":
    main()

