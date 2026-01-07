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
        source_db='source_database'
    )
    
    executor.migrate_site(
        site_info={'username': 'user1', 'siteName': 'Site 1'},
        tenant_db='tenant_user1',
        site_uuid='uuid-here'
    )
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


class MigrationExecutor:
    """Execute database migrations from field_mappings.json"""
    
    def __init__(self, mappings_file: str, source_conn, source_db: str, central_db: str = 'central_database'):
        """
        Initialize migration executor.
        
        Args:
            mappings_file: Path to field_mappings.json
            source_conn: PyMySQL connection to source database
            source_db: Source database name
            central_db: Central database name
        """
        self.source_conn = source_conn
        self.source_db = source_db
        self.central_db = central_db
        
        with open(mappings_file, 'r') as f:
            self.mappings = json.load(f)
        
        # Cache for ID mappings (username -> user_id, etc.)
        self.id_cache = {}
    
    def migrate_site(
        self,
        site_info: Dict[str, Any],
        tenant_db: str,
        site_uuid: str
    ) -> Dict[str, Any]:
        """
        Migrate a complete site based on field_mappings.json.
        
        This orchestrates the entire site migration:
        1. Registers site in central DB (for FK dependencies)
        2. Migrates all tables in dependency order
        3. Returns detailed stats
        
        Args:
            site_info: Dictionary with site data (must include 'username', 'siteName', etc.)
            tenant_db: Target tenant database name
            site_uuid: UUID for this site
        
        Returns:
            Dict with migration stats
        """
        stats = {
            'tenant_tables': 0,
            'central_tables': 0,
            'total_rows': 0,
            'errors': []
        }
        
        username = site_info.get('username')
        if not username:
            raise ValueError("site_info must contain 'username'")
        
        # Step 1: Register site in central DB (needed for FK constraints)
        try:
            self._register_site_in_central(site_info, tenant_db, site_uuid)
        except Exception as e:
            stats['errors'].append({'table': 'sites_registry', 'error': str(e)})
            return stats
        
        # Step 2: Build ID cache for this site (username -> user_id, etc.)
        self._build_id_cache(username, tenant_db)
        
        # Step 3: Migrate tables in dependency order
        migration_order = self._get_migration_order()
        
        for old_table in migration_order:
            if old_table not in self.mappings or old_table.startswith('_'):
                continue
            
            # Determine if this table applies to this site
            filters = self._get_site_filters(old_table, site_info)
            if filters is None:
                continue
            
            try:
                # Migrate to tenant DB
                tenant_stats = self.migrate_table(
                    old_table=old_table,
                    target_db=tenant_db,
                    target_db_type='tenant',
                    site_uuid=site_uuid,
                    filters=filters
                )
                if tenant_stats['migrated'] > 0:
                    stats['tenant_tables'] += 1
                    stats['total_rows'] += tenant_stats['migrated']
                
                # Migrate to central DB (if table has central targets)
                central_stats = self.migrate_table(
                    old_table=old_table,
                    target_db=self.central_db,
                    target_db_type='central',
                    site_uuid=site_uuid,
                    filters=filters
                )
                if central_stats['migrated'] > 0:
                    stats['central_tables'] += 1
                    stats['total_rows'] += central_stats['migrated']
                
            except Exception as e:
                stats['errors'].append({
                    'table': old_table,
                    'error': str(e)
                })
                print(f"Error migrating {old_table}: {e}")
        
        return stats
    
    def _register_site_in_central(self, site_info: Dict, tenant_db: str, site_uuid: str):
        """Register site in sites_registry (required for FK constraints)."""
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{self.central_db}`")
            cursor.execute("""
                INSERT INTO sites_registry (
                    site_uuid, database_name, site_name, site_email,
                    is_active, is_internal, created_by
                ) VALUES (%s, %s, %s, %s, TRUE, FALSE, 'migration')
                ON DUPLICATE KEY UPDATE 
                    site_name = VALUES(site_name),
                    site_email = VALUES(site_email)
            """, (
                site_uuid,
                tenant_db,
                site_info.get('siteName', site_info.get('username')),
                site_info.get('AdminEmailAddress', '')
            ))
            self.source_conn.commit()
    
    def _build_id_cache(self, username: str, tenant_db: str):
        """Build cache of ID mappings for this site."""
        self.id_cache = {}
        
        # Cache user_id mapping (username -> user_id in new tenant DB)
        try:
            with self.source_conn.cursor() as cursor:
                cursor.execute(f"USE `{tenant_db}`")
                cursor.execute("SELECT id, username FROM users WHERE username = %s", (username,))
                result = cursor.fetchone()
                if result:
                    self.id_cache['user_id'] = result['id']
        except:
            pass  # users table may not be populated yet
    
    def _get_migration_order(self) -> List[str]:
        """
        Return tables in dependency order.
        Parents must be migrated before children to satisfy FK constraints.
        """
        # Define dependency order (parents first)
        order = [
            # Core site/user data (no dependencies)
            'sysadmin_systemsettings',  # -> users, site
            
            # DICOM hierarchy (parent -> child)
            'patients',
            'studies',
            'series',
            'processing_jobs',
            'job_reports',
            'job_report_data',
            'dicom_tags',
            
            # Central tables (global, no site dependency)
            'services',
            'container_description',
            'user_licenses',
            'rsi_config',
            
            # Session/auth (depends on users)
            'session',
            'oauth_state',
            'output_routing',
            
            # Logs (depends on users)
            'devlog',
            'audit',
        ]
        
        # Add any tables not in order at the end
        for table in self.mappings.keys():
            if table not in order and not table.startswith('_'):
                order.append(table)
        
        return order
    
    def _get_site_filters(self, old_table: str, site_info: Dict) -> Optional[Dict[str, Any]]:
        """
        Determine filter criteria for a site-specific table.
        Returns None if table should be skipped for this site.
        """
        username = site_info.get('username')
        account_id = site_info.get('id')
        
        # Tables that filter by username
        username_tables = {
            'sysadmin_systemsettings', 'session', 'series', 'patients',
            'studies', 'processing_jobs', 'job_reports', 'job_report_data',
            'dicom_tags', 'devlog', 'output_routing', 'rsi_config',
            'user_licenses', 'oauth_state'
        }
        
        # Tables that filter by account_id
        account_id_tables = {'audit'}
        
        # Global tables (migrate once, no filter)
        global_tables = {
            'services', 'container_description', 'dicom_dictionary',
            'magnets', 'support_ticket_cache', 'ms365_tenant_config'
        }
        
        if old_table in username_tables:
            return {'username': username}
        elif old_table in account_id_tables:
            return {'account_id': account_id}
        elif old_table in global_tables:
            return {}  # No filter
        else:
            return None  # Skip unknown tables
    
    def migrate_table(
        self, 
        old_table: str, 
        target_db: str,
        target_db_type: str,
        site_uuid: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Migrate data from old_table to new schema based on field_mappings.json.
        
        This method:
        1. Fetches source data with filters
        2. Groups targets by table
        3. Builds INSERT statements with SQL transformations
        4. Executes migrations
        
        Args:
            old_table: Source table name
            target_db: Target database name
            target_db_type: 'tenant' or 'central'
            site_uuid: Site UUID for FK references
            filters: WHERE clause filters
        
        Returns:
            Dict with stats: {'migrated': N, 'skipped': M, 'errors': P}
        """
        if old_table not in self.mappings:
            return {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        field_mappings = self.mappings[old_table]
        
        # Fetch source data
        source_rows = self._fetch_source_data(old_table, filters)
        if not source_rows:
            return {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Group targets by table
        target_groups = self._group_targets(field_mappings, target_db_type)
        if not target_groups:
            return {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        stats = {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Migrate to each target table
        for target_table, field_list in target_groups.items():
            try:
                count = self._migrate_to_target(
                    target_db=target_db,
                    target_table=target_table,
                    field_list=field_list,
                    source_rows=source_rows,
                    site_uuid=site_uuid
                )
                stats['migrated'] += count
            except Exception as e:
                print(f"Error migrating to {target_table}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _fetch_source_data(self, old_table: str, filters: Optional[Dict]) -> List[Dict]:
        """Fetch source data with filters."""
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{self.source_db}`")
            
            where_clause = ""
            where_params = []
            if filters:
                conditions = [f"`{k}` = %s" for k in filters.keys()]
                where_clause = " WHERE " + " AND ".join(conditions)
                where_params = list(filters.values())
            
            cursor.execute(f"SELECT * FROM `{old_table}`{where_clause}", where_params)
            return cursor.fetchall()
    
    def _group_targets(self, field_mappings: Dict, target_db_type: str) -> Dict[str, List]:
        """Group field targets by target table."""
        target_groups = {}
        
        for old_field, mapping in field_mappings.items():
            if old_field.startswith('_'):
                continue
            
            if not isinstance(mapping, dict) or 'targets' not in mapping:
                continue
            
            for target in mapping['targets']:
                db = target.get('db', 'tenant')
                if db != target_db_type:
                    continue
                
                target_table = target['table']
                if target_table not in target_groups:
                    target_groups[target_table] = []
                
                target_groups[target_table].append({
                    'old_field': old_field,
                    'new_field': target['column'],
                    'sql': target.get('sql'),
                    'condition': target.get('condition')
                })
        
        return target_groups
    
    def _migrate_to_target(
        self,
        target_db: str,
        target_table: str,
        field_list: List[Dict],
        source_rows: List[Dict],
        site_uuid: str
    ) -> int:
        """Migrate rows to a specific target table."""
        if not source_rows:
            return 0
        
        migrated_count = 0
        
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{target_db}`")
            
            for row in source_rows:
                # Build INSERT data for this row
                insert_data = {}
                
                for field_info in field_list:
                    old_field = field_info['old_field']
                    new_field = field_info['new_field']
                    sql_transform = field_info.get('sql')
                    condition = field_info.get('condition')
                    
                    # Skip if condition not met
                    if condition and not self._eval_condition(condition, row):
                        continue
                    
                    # Get value with transformation
                    value = self._get_transformed_value(
                        row, old_field, sql_transform, target_db, target_table
                    )
                    
                    insert_data[new_field] = value
                
                # Add site_uuid if target table has it
                if target_table in ['site', 'users', 'patients', 'studies', 'series', 
                                   'processing_jobs', 'devlog', 'audit_log']:
                    # Most tables in tenant DB don't need site_uuid
                    # Only central DB tables need it
                    pass
                
                # Skip if no data to insert
                if not insert_data:
                    continue
                
                # Build and execute INSERT
                try:
                    columns = list(insert_data.keys())
                    placeholders = ["%s"] * len(columns)
                    values = list(insert_data.values())
                    
                    sql = f"""
                        INSERT INTO `{target_table}` 
                        ({', '.join(f'`{c}`' for c in columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    cursor.execute(sql, values)
                    migrated_count += 1
                    
                except Exception as e:
                    print(f"Error inserting into {target_table}: {e}")
                    print(f"Data: {insert_data}")
                    raise
            
            self.source_conn.commit()
        
        return migrated_count
    
    def _get_transformed_value(
        self, row: Dict, old_field: str, sql_transform: Optional[str], 
        target_db: str, target_table: str
    ) -> Any:
        """Get field value with optional SQL transformation."""
        base_value = row.get(old_field)
        
        # If no transformation, return base value
        if not sql_transform:
            return base_value
        
        # Execute SQL transformation
        # SQL transform format: "CASE WHEN condition THEN value ELSE other END"
        # For simplicity, we'll evaluate simple CASE statements in Python
        
        # Handle CASE WHEN statements
        if 'CASE' in sql_transform.upper() and 'WHEN' in sql_transform.upper():
            return self._eval_case_statement(sql_transform, row)
        
        # Handle simple expressions
        return self._eval_expression(sql_transform, row)
    
    def _eval_case_statement(self, sql: str, row: Dict) -> Any:
        """Evaluate a CASE WHEN statement."""
        # Simple parser for CASE statements
        # Format: CASE WHEN condition THEN value ELSE other END
        
        # Extract conditions and values
        pattern = r'WHEN\s+(.+?)\s+THEN\s+(.+?)(?:\s+WHEN|\s+ELSE|\s+END)'
        matches = re.findall(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        for condition, value in matches:
            if self._eval_sql_condition(condition, row):
                return self._eval_sql_value(value, row)
        
        # Handle ELSE clause
        else_match = re.search(r'ELSE\s+(.+?)\s+END', sql, re.IGNORECASE | re.DOTALL)
        if else_match:
            return self._eval_sql_value(else_match.group(1), row)
        
        return None
    
    def _eval_sql_condition(self, condition: str, row: Dict) -> bool:
        """Evaluate a SQL condition."""
        # Simple condition evaluator
        # Supports: field = 'value', field != 'value', field IS NULL, etc.
        
        condition = condition.strip()
        
        # Handle = comparison
        if ' = ' in condition:
            field, value = condition.split(' = ', 1)
            field = field.strip().replace('ss.', '').replace('`', '')
            value = value.strip().strip("'")
            return str(row.get(field)) == value
        
        # Handle != comparison
        if ' != ' in condition or ' <> ' in condition:
            sep = ' != ' if ' != ' in condition else ' <> '
            field, value = condition.split(sep, 1)
            field = field.strip().replace('ss.', '').replace('`', '')
            value = value.strip().strip("'")
            return str(row.get(field)) != value
        
        # Handle IS NULL
        if 'IS NULL' in condition.upper():
            field = condition.replace('IS NULL', '').strip().replace('ss.', '').replace('`', '')
            return row.get(field) is None
        
        return False
    
    def _eval_sql_value(self, value: str, row: Dict) -> Any:
        """Evaluate a SQL value expression."""
        value = value.strip()
        
        # Handle NULL
        if value.upper() == 'NULL':
            return None
        
        # Handle quoted strings
        if value.startswith("'") and value.endswith("'"):
            return value.strip("'")
        
        # Handle field references
        if not value.startswith("'"):
            field = value.replace('ss.', '').replace('`', '')
            return row.get(field)
        
        return value
    
    def _eval_expression(self, expr: str, row: Dict) -> Any:
        """Evaluate a simple SQL expression."""
        # Handle field references
        for field in row.keys():
            expr = expr.replace(f'ss.{field}', f"row['{field}']")
        
        # Simple evaluation (be careful in production!)
        try:
            return eval(expr, {'row': row})
        except:
            return None
    
    def _eval_condition(self, condition: str, row: Dict) -> bool:
        """Evaluate a condition for conditional mapping."""
        return self._eval_sql_condition(condition, row)
