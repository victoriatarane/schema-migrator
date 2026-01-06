#!/usr/bin/env python3
"""
Schema Migration Executor
=========================

Executes migrations defined in field_mappings.json.
This makes JSON the single source of truth for both visualization AND execution.

Usage:
    from schema_migrator import MigrationExecutor
    
    executor = MigrationExecutor(
        mappings_file='field_mappings.json',
        source_conn=conn,
        source_db='legacy_db'
    )
    
    executor.migrate_table(
        old_table='users',
        target_db='app_tenant_abc',
        target_db_type='tenant',
        filters={'is_active': 1, 'tenant_id': 123}
    )
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


class MigrationExecutor:
    """Execute database migrations from field_mappings.json"""
    
    def __init__(self, mappings_file: str, source_conn, source_db: str):
        """
        Initialize migration executor.
        
        Args:
            mappings_file: Path to field_mappings.json
            source_conn: PyMySQL connection to source database
            source_db: Source database name (e.g., 'legacy_db')
        """
        self.source_conn = source_conn
        self.source_db = source_db
        
        with open(mappings_file, 'r') as f:
            self.mappings = json.load(f)
    
    def migrate_table(
        self, 
        old_table: str, 
        target_db: str,
        target_db_type: str = 'tenant',
        filters: Optional[Dict[str, Any]] = None,
        id_map: Optional[Dict[int, int]] = None
    ) -> Dict[str, Any]:
        """
        Migrate data from old_table to new schema based on field_mappings.json.
        
        Args:
            old_table: Source table name (e.g., 'users')
            target_db: Target database name (e.g., 'app_tenant_abc')
            target_db_type: 'tenant' or 'central'
            filters: WHERE clause filters (e.g., {'internal_user': 0, 'id': 123})
            id_map: Map old IDs to new IDs for FK lookups (e.g., {old_user_id: new_user_id})
        
        Returns:
            Dict with migration stats: {'migrated': 10, 'skipped': 2, 'errors': 0}
        """
        if old_table not in self.mappings:
            raise ValueError(f"No mappings found for table '{old_table}'")
        
        # Get field mappings for this table
        field_mappings = self.mappings[old_table]
        
        # Build SELECT query for source data
        columns = [col for col in field_mappings.keys() if not col.startswith('_')]
        
        where_clause = ""
        where_params = []
        if filters:
            conditions = [f"{k} = %s" for k in filters.keys()]
            where_clause = " WHERE " + " AND ".join(conditions)
            where_params = list(filters.values())
        
        # Fetch source data
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE {self.source_db}")
            cursor.execute(f"""
                SELECT * FROM {old_table}
                {where_clause}
            """, where_params)
            source_rows = cursor.fetchall()
        
        if not source_rows:
            return {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Group targets by (db_type, table) to batch inserts
        target_groups = self._group_targets_by_table(field_mappings, target_db_type)
        
        stats = {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # For each target table, build and execute INSERT
        for (db_type, target_table), field_list in target_groups.items():
            try:
                self._migrate_to_target_table(
                    target_db=target_db,
                    target_table=target_table,
                    field_list=field_list,
                    source_rows=source_rows,
                    id_map=id_map
                )
                stats['migrated'] += len(source_rows)
            except Exception as e:
                print(f"Error migrating to {target_table}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _group_targets_by_table(
        self, 
        field_mappings: Dict, 
        target_db_type: str
    ) -> Dict[Tuple[str, str], List[Dict]]:
        """
        Group field mappings by (db_type, table_name).
        
        Returns:
            {('tenant', 'users'): [
                {'old_field': 'username', 'column': 'username', 'sql': None},
                {'old_field': 'AdminPassword', 'column': 'password_hash', 'sql': '...'}
            ]}
        """
        groups = {}
        
        for old_field, mapping in field_mappings.items():
            if old_field.startswith('_') or mapping.get('deprecated'):
                continue
            
            targets = mapping.get('targets', [])
            if not targets and mapping.get('target'):
                # Handle old single-target format
                parts = mapping['target'].split('.')
                if len(parts) == 2:
                    targets = [{
                        'db': 'tenant',
                        'table': parts[0],
                        'column': parts[1],
                        'sql': mapping.get('sql')
                    }]
            
            for target in targets:
                if target['db'] != target_db_type:
                    continue  # Skip if not matching target database type
                
                key = (target['db'], target['table'])
                if key not in groups:
                    groups[key] = []
                
                groups[key].append({
                    'old_field': old_field,
                    'column': target['column'],
                    'sql': target.get('sql'),
                    'notes': mapping.get('notes')
                })
        
        return groups
    
    def _migrate_to_target_table(
        self,
        target_db: str,
        target_table: str,
        field_list: List[Dict],
        source_rows: List[Dict],
        id_map: Optional[Dict[int, int]] = None
    ):
        """
        Execute INSERT for a specific target table.
        
        Args:
            target_db: Target database name
            target_table: Target table name
            field_list: List of field mappings for this table
            source_rows: Source data rows
            id_map: Optional ID mapping for FK resolution
        """
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE {target_db}")
            
            for row in source_rows:
                # Build column list and values
                columns = []
                values = []
                
                for field_info in field_list:
                    old_field = field_info['old_field']
                    column = field_info['column']
                    sql_expr = field_info['sql']
                    
                    columns.append(column)
                    
                    # Evaluate SQL expression if provided
                    if sql_expr:
                        value = self._eval_sql_expression(sql_expr, row, id_map)
                    else:
                        value = row.get(old_field)
                    
                    values.append(value)
                
                # Check if row already exists (by legacy ID if available)
                # TODO: Make this configurable per table
                
                # Execute INSERT
                placeholders = ', '.join(['%s'] * len(values))
                col_list = ', '.join(columns)
                
                cursor.execute(f"""
                    INSERT INTO {target_table} ({col_list})
                    VALUES ({placeholders})
                """, values)
            
            self.source_conn.commit()
    
    def _eval_sql_expression(
        self, 
        sql_expr: str, 
        row: Dict[str, Any], 
        id_map: Optional[Dict[int, int]] = None
    ) -> Any:
        """
        Evaluate SQL expression against a source row.
        
        Examples:
            "ss.AdminPassword = '!!!LOCKED!!!'" → True/False
            "CASE WHEN ss.AdminPassword = '!!!LOCKED!!!' THEN NULL ELSE ss.AdminPassword END"
        
        Args:
            sql_expr: SQL expression string
            row: Source data row
            id_map: Optional ID mapping for FK lookups
        
        Returns:
            Evaluated value
        """
        # Simple string replacement for table aliases (ss. → row value)
        # This is a simplified implementation - full SQL parser would be better
        
        # Replace table.column references with Python row access
        expr = sql_expr
        
        # Handle CASE expressions
        if 'CASE' in expr.upper():
            return self._eval_case_expression(expr, row)
        
        # Handle simple comparisons
        if '=' in expr:
            # e.g., "ss.AdminPassword = '!!!LOCKED!!!'"
            parts = expr.split('=')
            if len(parts) == 2:
                field_ref = parts[0].strip().split('.')[-1]
                compare_val = parts[1].strip().strip("'")
                return row.get(field_ref) == compare_val
        
        # Handle field references
        if '.' in expr:
            field_name = expr.split('.')[-1]
            return row.get(field_name)
        
        # Return as-is if can't parse
        return expr
    
    def _eval_case_expression(self, case_expr: str, row: Dict[str, Any]) -> Any:
        """
        Evaluate CASE WHEN ... THEN ... ELSE ... END expression.
        
        Simplified parser for common patterns.
        """
        # Pattern: CASE WHEN condition THEN value ELSE value END
        match = re.search(
            r'CASE\s+WHEN\s+(.+?)\s+THEN\s+(.+?)\s+ELSE\s+(.+?)\s+END',
            case_expr,
            re.IGNORECASE | re.DOTALL
        )
        
        if not match:
            return None
        
        condition, then_val, else_val = match.groups()
        
        # Evaluate condition
        condition_result = self._eval_sql_expression(condition, row, None)
        
        if condition_result:
            # Return THEN value
            if then_val.upper() == 'NULL':
                return None
            return then_val.strip().strip("'")
        else:
            # Return ELSE value
            if else_val.upper() == 'NULL':
                return None
            # Check if it's a field reference
            if '.' in else_val:
                field_name = else_val.split('.')[-1]
                return row.get(field_name)
            return else_val.strip().strip("'")
        
        return None


# Convenience function
def migrate_from_json(
    mappings_file: str,
    source_conn,
    source_db: str,
    old_table: str,
    target_db: str,
    target_db_type: str = 'tenant',
    filters: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    One-liner to execute migration from JSON.
    
    Example:
        stats = migrate_from_json(
            mappings_file='field_mappings.json',
            source_conn=conn,
            source_db='legacy_db',
            old_table='users',
            target_db='app_tenant_abc',
            filters={'is_active': 1, 'tenant_id': 123}
        )
    """
    executor = MigrationExecutor(mappings_file, source_conn, source_db)
    return executor.migrate_table(old_table, target_db, target_db_type, filters)

