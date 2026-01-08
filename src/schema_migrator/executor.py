#!/usr/bin/env python3
"""
Schema Migration Executor - Production Ready
============================================

Executes migrations defined in field_mappings.json.
Single source of truth for both visualization AND execution.

Key Features:
- Reads field_mappings.json for all transformations
- Handles complex SQL transformations
- Manages ID lookups and caching (username -> user_id)
- Respects FK dependencies
- Production-grade error handling and logging
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pymysql

# Configure logging
logger = logging.getLogger(__name__)


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
        
        # Cache for unique constraint detection: {db_name.table_name: [unique_columns]}
        self.unique_constraints_cache: Dict[str, List[List[str]]] = {}
        
        # Universal ID mapping cache: { 'table_name': { 'lookup_column': { old_value: new_id } } }
        # Example: { 'users': { 'username': { 'admin': 1, 'user2': 2 } } }
        #          { 'patients': { 'patient_id': { 'PAT001': 1, 'PAT002': 2 } } }
        self.id_mappings = {}
        
        # Track which tables have been migrated (for dependency resolution)
        self.migrated_tables = set()
    
    def migrate_site(
        self,
        site_info: Dict[str, Any],
        tenant_db: str,
        site_uuid: str
    ) -> Dict[str, Any]:
        """
        Migrate a complete site based on field_mappings.json.
        
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
        
        logger.info(f"Starting migration for site: {site_info.get('siteName', username)}")
        logger.debug(f"Username: {username}, Tenant DB: {tenant_db}, Site UUID: {site_uuid}")
        
        # Step 1: Register site in central DB (needed for FK constraints)
        try:
            self._register_site_in_central(site_info, tenant_db, site_uuid)
        except Exception as e:
            stats['errors'].append({'table': 'sites_registry', 'error': str(e)})
            logger.error(f"Failed to register site: {e}")
            return stats
        
        # Step 2: Get migration order (respecting FK dependencies)
        migration_order = self._get_migration_order()
        
        # Step 3: Migrate each table
        for old_table in migration_order:
            if old_table not in self.mappings or old_table.startswith('_'):
                continue
            
            # Determine if this table applies to this site
            filters = self._get_site_filters(old_table, site_info)
            if filters is None:
                continue  # Skip tables not applicable to this site
            
            print(f"\n📋 Migrating table: {old_table}")
            
            try:
                # Migrate to tenant DB
                tenant_stats = self.migrate_table(
                    old_table=old_table,
                    target_db=tenant_db,
                    target_db_type='tenant',
                    site_uuid=site_uuid,
                    site_info=site_info,
                    filters=filters
                )
                if tenant_stats['migrated'] > 0:
                    stats['tenant_tables'] += 1
                    stats['total_rows'] += tenant_stats['migrated']
                    logger.info(f"Tenant: {tenant_stats['migrated']} rows")
                
                # Migrate to central DB (if table has central targets)
                central_stats = self.migrate_table(
                    old_table=old_table,
                    target_db=self.central_db,
                    target_db_type='central',
                    site_uuid=site_uuid,
                    site_info=site_info,
                    filters=filters
                )
                if central_stats['migrated'] > 0:
                    stats['central_tables'] += 1
                    stats['total_rows'] += central_stats['migrated']
                    logger.info(f"Central: {central_stats['migrated']} rows")
                
                if tenant_stats['migrated'] == 0 and central_stats['migrated'] == 0:
                    logger.debug(f"No data to migrate")
                
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback_str = traceback.format_exc()
                stats['errors'].append({'table': old_table, 'error': error_msg})
                logger.error(f"Error: {error_msg}")
                logger.debug(f"Traceback:\n{traceback_str[:500]}")
        
        print(f"\n✅ Migration complete for {username}")
        logger.info(f"Rows migrated: {stats['total_rows']}")
        logger.info(f"Errors: {len(stats['errors'])}")
        
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
            logger.info(f"Registered in sites_registry")
    
    def _get_migration_order(self) -> List[str]:
        """
        Return tables in dependency order.
        Parents must be migrated before children to satisfy FK constraints.
        """
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
        """Determine filter criteria for a site-specific table."""
        username = site_info.get('username')
        account_id = site_info.get('id')
        
        # Check which columns actually exist in the old table
        # Use regular cursor (not DictCursor) for SHOW COLUMNS
        try:
            with self.source_conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(f"USE `{self.source_db}`")
                cursor.execute(f"SHOW COLUMNS FROM `{old_table}`")
                columns = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.warning(f"Could not check columns for {old_table}: {e}")
            return None
        
        # Determine filter based on available columns
        if 'username' in columns:
            return {'username': username}
        elif 'account_id' in columns:
            return {'account_id': account_id}
        else:
            # For DICOM tables without username, we skip them here
            # They should be migrated by the hardcoded functions that understand the relationships
            return None  # Indicates: skip this table in JSON-driven migration
    
    def migrate_table(
        self, 
        old_table: str, 
        target_db: str,
        target_db_type: str,
        site_uuid: str,
        site_info: Dict,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Migrate data from old_table to new schema based on field_mappings.json.
        
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
        
        # Sort target tables by FK dependency order
        sorted_tables = self._sort_targets_by_dependency(list(target_groups.keys()))
        
        # Migrate to each target table in dependency order
        for target_table in sorted_tables:
            field_list = target_groups[target_table]
            try:
                count = self._migrate_to_target(
                    old_table=old_table,
                    target_db=target_db,
                    target_table=target_table,
                    field_list=field_list,
                    source_rows=source_rows,
                    site_uuid=site_uuid,
                    site_info=site_info
                )
                stats['migrated'] += count
            except Exception as e:
                logger.error(f"Error migrating to {target_table}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _fetch_source_data(self, old_table: str, filters: Optional[Dict]) -> List[Dict]:
        """Fetch source data with filters."""
        with self.source_conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"USE `{self.source_db}`")
            
            where_clause = ""
            where_params = []
            if filters:
                conditions = [f"`{k}` = %s" for k in filters.keys()]
                where_clause = " WHERE " + " AND ".join(conditions)
                where_params = list(filters.values())
            
            query = f"SELECT * FROM `{old_table}`{where_clause}"
            cursor.execute(query, where_params)
            rows = cursor.fetchall()
            
            return rows if rows else []
    
    def _group_targets(self, field_mappings: Dict, target_db_type: str) -> Dict[str, List]:
        """
        Group field targets by target table.
        Handles BOTH old and new mapping formats:
        - Old: {"target": "table.column"}
        - New: {"targets": [{"db": "tenant", "table": "...", "column": "..."}]}
        """
        target_groups = {}
        
        for old_field, mapping in field_mappings.items():
            if old_field.startswith('_'):
                continue
            
            if not isinstance(mapping, dict):
                continue
            
            # Handle NEW format: {"targets": [...]}
            if 'targets' in mapping:
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
                        'condition': target.get('condition'),
                        'lookup_chain': target.get('lookup_chain')
                    })
            
            # Handle OLD format: {"target": "table.column"}
            elif 'target' in mapping:
                target_str = mapping['target']
                if target_str and isinstance(target_str, str) and '.' in target_str:
                    target_table, target_column = target_str.split('.', 1)
                    
                    # Old format is always tenant DB (no central DB distinction in old format)
                    if target_db_type != 'tenant':
                        continue
                    
                    if target_table not in target_groups:
                        target_groups[target_table] = []
                    
                    target_groups[target_table].append({
                        'old_field': old_field,
                        'new_field': target_column,
                        'sql': mapping.get('sql'),
                        'condition': mapping.get('condition'),
                        'lookup_chain': mapping.get('lookup_chain')
                    })
        
        return target_groups
    
    def _sort_targets_by_dependency(self, tables: List[str]) -> List[str]:
        """
        Sort target tables by FK dependency order.
        Tables without dependencies come first, tables with dependencies come later.
        
        This ensures that when migrating data from a single source table to multiple
        target tables (e.g., series -> patients, studies, series, processing_jobs),
        we create records in the correct order so FKs can be resolved.
        """
        # Define known FK dependencies
        # Format: {dependent_table: [tables_it_depends_on]}
        dependencies = {
            'processing_jobs': ['series', 'users'],
            'series': ['studies'],
            'studies': ['patients'],
            'job_reports': ['processing_jobs'],
            'job_report_data': ['job_reports'],
            'sessions': ['users'],
            'devlog': ['users'],
            'audit_log': ['users'],
            'oauth_state': ['users'],
            'rsi_config': ['services'],  # In central DB
            'user_licenses': ['services'],  # In central DB
        }
        
        # Create a dependency graph for tables in this migration
        in_migration = set(tables)
        dep_graph = {}
        for table in tables:
            dep_graph[table] = [dep for dep in dependencies.get(table, []) if dep in in_migration]
        
        # Topological sort
        sorted_tables = []
        visited = set()
        temp_mark = set()
        
        def visit(table):
            if table in temp_mark:
                # Circular dependency detected, just proceed
                return
            if table in visited:
                return
            
            temp_mark.add(table)
            for dep in dep_graph.get(table, []):
                visit(dep)
            temp_mark.remove(table)
            visited.add(table)
            sorted_tables.append(table)
        
        for table in tables:
            if table not in visited:
                visit(table)
        
        return sorted_tables
    
    def _get_unique_constraints(self, db_name: str, table_name: str) -> List[List[str]]:
        """
        Get unique constraint columns for a table.
        Returns list of lists: [[col1, col2], [col3]] for composite and single unique keys.
        Caches results for performance.
        """
        cache_key = f"{db_name}.{table_name}"
        if cache_key in self.unique_constraints_cache:
            return self.unique_constraints_cache[cache_key]
        
        unique_constraints = []
        
        try:
            with self.source_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(f"USE `{db_name}`")
                cursor.execute(f"""
                    SELECT 
                        INDEX_NAME,
                        GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as columns
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                      AND NON_UNIQUE = 0
                      AND INDEX_NAME != 'PRIMARY'
                    GROUP BY INDEX_NAME
                """, (db_name, table_name))
                
                for row in cursor.fetchall():
                    cols = row['columns'].split(',')
                    unique_constraints.append(cols)
        
        except Exception as e:
            logger.warning(f"Could not detect unique constraints for {cache_key}: {e}")
        
        self.unique_constraints_cache[cache_key] = unique_constraints
        return unique_constraints
    
    def _migrate_to_target(
        self,
        old_table: str,
        target_db: str,
        target_table: str,
        field_list: List[Dict],
        source_rows: List[Dict],
        site_uuid: str,
        site_info: Dict
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
                    lookup_chain = field_info.get('lookup_chain')
                    
                    # Skip if condition not met
                    if condition and not self._eval_condition(condition, row):
                        continue
                    
                    # Get value (with transformation if specified)
                    value = self._get_field_value(
                        row=row,
                        old_field=old_field,
                        new_field=new_field,
                        sql_transform=sql_transform,
                        old_table=old_table,
                        target_table=target_table,
                        target_db=target_db,
                        site_info=site_info,
                        lookup_chain=lookup_chain
                    )
                    
                    insert_data[new_field] = value
                
                # Skip if no data to insert
                if not insert_data:
                    continue
                
                # Add site_uuid for central DB tables
                if target_db == self.central_db and 'site_uuid' not in insert_data:
                    # Check if table has site_uuid column
                    if target_table in ['rsi_config', 'user_licenses', 'devlog', 'total_activity_metrics']:
                        insert_data['site_uuid'] = site_uuid
                
                # Build and execute INSERT (with UPSERT for deduplication)
                try:
                    columns = list(insert_data.keys())
                    placeholders = ["%s"] * len(columns)
                    values = list(insert_data.values())
                    
                    # Detect unique constraints for deduplication
                    unique_constraints = self._get_unique_constraints(target_db, target_table)
                    
                    # Build INSERT with ON DUPLICATE KEY UPDATE if unique constraints exist
                    sql = f"""
                        INSERT INTO `{target_table}` 
                        ({', '.join(f'`{c}`' for c in columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    if unique_constraints:
                        # Add UPSERT logic: update non-PK columns on duplicate
                        update_cols = [c for c in columns if c not in ['id', 'created_at']]
                        if update_cols:
                            sql += " ON DUPLICATE KEY UPDATE "
                            sql += ', '.join(f'`{c}` = VALUES(`{c}`)' for c in update_cols)
                    
                    cursor.execute(sql, values)
                    
                    # Get the inserted/updated row ID
                    row_id = cursor.lastrowid
                    
                    # If lastrowid is 0, we updated an existing row - need to fetch its ID
                    if row_id == 0 and unique_constraints:
                        # Find the ID by querying with unique constraint values
                        for unique_cols in unique_constraints:
                            if all(col in insert_data for col in unique_cols):
                                where_clause = ' AND '.join(f'`{col}` = %s' for col in unique_cols)
                                where_values = [insert_data[col] for col in unique_cols]
                                cursor.execute(f"SELECT id FROM `{target_table}` WHERE {where_clause}", where_values)
                                result = cursor.fetchone()
                                if result:
                                    row_id = result[0]
                                    break
                    
                    # Cache ID mappings for FK lookups
                    self._cache_id_mapping(old_table, target_table, row, row_id, insert_data)
                    
                    migrated_count += 1
                    
                except Exception as e:
                    # Don't raise - just log and continue with next row
                    logger.warning(f"Skipped row: {str(e)[:100]}")
            
            self.source_conn.commit()
        
        return migrated_count
    
    def _get_field_value(
        self,
        row: Dict,
        old_field: str,
        new_field: str,
        sql_transform: Optional[str],
        old_table: str,
        target_table: str,
        target_db: str,
        site_info: Dict,
        lookup_chain: Optional[List[Dict]] = None
    ) -> Any:
        """
        Extract field value from source row with optional transformation.
        
        This is the KEY method that makes the executor work correctly.
        
        Supports:
        - Direct field mapping
        - SQL transformations (CASE WHEN, etc.)
        - FK chain resolution (multi-level lookups)
        """
        # DEBUG: Log input parameters
        if new_field == 'user_id':
            logger.debug(f"_get_field_value called: old_field={old_field}, new_field={new_field}, lookup_chain={bool(lookup_chain)}")
        
        # 1. Check if this field requires FK chain resolution
        if lookup_chain and isinstance(lookup_chain, list):
            logger.debug(f"Resolving FK chain for {target_table}.{new_field}...")
            resolved_id = self._resolve_fk_chain(row, lookup_chain, target_db)
            if resolved_id is not None:
                logger.debug(f"FK resolved: {new_field} = {resolved_id}")
                return resolved_id
            else:
                logger.debug(f"FK chain resolution failed for {target_table}.{new_field}")
                # When FK resolution fails, return None (field should be nullable)
                return None
        
        # 2. Get base value from source row
        base_value = row.get(old_field)
        
        # 3. Universal FK resolution: Check if we have a cached mapping
        if new_field == 'user_id':
            # Try to resolve from cached mappings
            if 'users' in self.id_mappings and 'username' in self.id_mappings['users']:
                username = row.get('username', base_value)
                if username and username in self.id_mappings['users']['username']:
                    return self.id_mappings['users']['username'][username]
            # If not cached and no lookup_chain, return None
            if not lookup_chain:
                return None
        
        # 4. If no SQL transformation, return base value
        if not sql_transform or not isinstance(sql_transform, str):
            return base_value
        
        # 5. SKIP full INSERT statements - these are for the old hardcoded script, not the executor
        if sql_transform and 'INSERT INTO' in sql_transform.upper():
            return base_value
        
        # 6. Handle SQL transformations
        return self._evaluate_sql_transform(sql_transform, row, site_info)
    
    def _evaluate_sql_transform(self, sql_transform: str, row: Dict, site_info: Dict) -> Any:
        """
        Evaluate SQL transformation expressions.
        
        Supports:
        - CASE WHEN ... THEN ... ELSE ... END
        - Simple column references
        - NULL
        - Literal values
        """
        if not sql_transform or not isinstance(sql_transform, str):
            return None
        
        sql = sql_transform.strip()
        
        # Handle CASE WHEN statements
        if sql.upper().startswith('CASE'):
            return self._eval_case_statement(sql, row)
        
        # Handle simple SELECT statements (extract just the column reference)
        if sql.upper().startswith('SELECT'):
            # Extract column name: "SELECT username FROM table WHERE..." -> "username"
            match = re.match(r'SELECT\s+(\w+)', sql, re.IGNORECASE)
            if match:
                col_name = match.group(1)
                return row.get(col_name)
        
        # Handle direct column references
        return row.get(sql)
    
    def _eval_case_statement(self, sql: str, row: Dict) -> Any:
        """Evaluate CASE WHEN statement."""
        # Extract WHEN clauses
        pattern = r'WHEN\s+(.+?)\s+THEN\s+(.+?)(?:\s+WHEN|\s+ELSE|\s+END)'
        matches = re.findall(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        for condition, value in matches:
            if self._eval_condition(condition.strip(), row):
                return self._eval_value(value.strip(), row)
        
        # Handle ELSE clause
        else_match = re.search(r'ELSE\s+(.+?)\s+END', sql, re.IGNORECASE | re.DOTALL)
        if else_match:
            return self._eval_value(else_match.group(1).strip(), row)
        
        return None
    
    def _eval_condition(self, condition: str, row: Dict) -> bool:
        """Evaluate a SQL condition."""
        if not condition or not isinstance(condition, str):
            return True  # No condition means always include
        
        # Handle = comparison
        if ' = ' in condition:
            parts = condition.split(' = ', 1)
            left = self._eval_value(parts[0].strip(), row)
            right = self._eval_value(parts[1].strip(), row)
            return str(left) == str(right)
        
        # Handle != or <> comparison
        if ' != ' in condition or ' <> ' in condition:
            sep = ' != ' if ' != ' in condition else ' <> '
            parts = condition.split(sep, 1)
            left = self._eval_value(parts[0].strip(), row)
            right = self._eval_value(parts[1].strip(), row)
            return str(left) != str(right)
        
        # Handle IS NULL
        if 'IS NULL' in condition.upper():
            col = condition.replace('IS NULL', '').replace('is null', '').strip()
            col = col.replace('ss.', '').replace('`', '')
            return row.get(col) is None
        
        return False
    
    def _eval_value(self, value: str, row: Dict) -> Any:
        """Evaluate a SQL value expression."""
        value = value.strip()
        
        # Handle NULL
        if value.upper() == 'NULL':
            return None
        
        # Handle quoted strings
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
        
        # Handle table-prefixed column references (ss.field -> field)
        if '.' in value:
            value = value.split('.')[-1]
        
        # Remove backticks
        value = value.replace('`', '')
        
        # Try to get from row
        return row.get(value, value)
    
    def _cache_id_mapping(
        self,
        old_table: str,
        target_table: str,
        source_row: Dict,
        new_id: int,
        inserted_data: Dict
    ):
        """
        Universal ID mapping cache.
        
        Stores mappings for ALL unique identifiers from any table to enable
        complex FK chain resolution.
        
        Structure: { 'table_name': { 'lookup_column': { old_value: new_id } } }
        """
        if not new_id:
            return
        
        # Initialize table entry if needed
        if target_table not in self.id_mappings:
            self.id_mappings[target_table] = {}
        
        # Cache common unique identifiers (can be extended for any table)
        unique_columns_to_cache = []
        
        # For ALL tables: cache the auto-increment 'id' column from old schema
        if 'id' in source_row and source_row['id']:
            unique_columns_to_cache.append(('id', source_row['id']))
        
        # For tables with natural keys: cache those too
        if 'username' in inserted_data and inserted_data['username']:
            unique_columns_to_cache.append(('username', inserted_data['username']))
        
        if 'patient_id' in inserted_data and inserted_data['patient_id']:
            unique_columns_to_cache.append(('patient_id', inserted_data['patient_id']))
        
        if 'study_instance_uid' in inserted_data and inserted_data['study_instance_uid']:
            unique_columns_to_cache.append(('study_instance_uid', inserted_data['study_instance_uid']))
        
        if 'series_instance_uid' in inserted_data and inserted_data['series_instance_uid']:
            unique_columns_to_cache.append(('series_instance_uid', inserted_data['series_instance_uid']))
        
        # Store all mappings
        for lookup_col, old_value in unique_columns_to_cache:
            if lookup_col not in self.id_mappings[target_table]:
                self.id_mappings[target_table][lookup_col] = {}
            self.id_mappings[target_table][lookup_col][old_value] = new_id
    
    def _resolve_fk_chain(
        self,
        source_row: Dict,
        lookup_chain: List[Dict[str, str]],
        target_db: str
    ) -> Optional[int]:
        """
        Universal FK chain resolver.
        
        Resolves multi-level FK relationships across tables.
        
        Example lookup_chain:
        [
            {'old_table': 'series', 'old_column': 'PatientID', 'lookup_in': 'patients'},
            {'old_table': 'patients', 'old_column': 'username', 'new_table': 'users', 'new_column': 'username'}
        ]
        
        This would:
        1. Get series.PatientID value from source_row
        2. Look up that PatientID in old patients table to get username
        3. Look up that username in new users table to get user_id
        
        Args:
            source_row: Current row being migrated
            lookup_chain: List of lookup steps
            target_db: Target database name for final FK resolution
        
        Returns:
            Resolved ID or None if lookup fails
        """
        if not lookup_chain or not isinstance(lookup_chain, list):
            return None
        
        current_value = None
        
        for step_idx, step in enumerate(lookup_chain):
            old_table = step.get('old_table')
            old_column = step.get('old_column')
            lookup_in = step.get('lookup_in')       # Old schema table to look in
            lookup_column = step.get('lookup_column') # Column to match in old table
            return_column = step.get('return_column') # Column to return from old table
            new_table = step.get('new_table')        # New schema table to look in
            new_column = step.get('new_column')      # Column to match in new table
            
            logger.debug(f"Step {step_idx}: old_col={old_column}, lookup_in={lookup_in}, new_table={new_table}")
            
            # Step 1: Get value from current context
            if step_idx == 0:
                # First step: get value from source_row
                current_value = source_row.get(old_column)
                logger.debug(f"Got value from source row: '{current_value}'")
                if not current_value:
                    logger.debug(f"No value in source row for column '{old_column}'")
                    return None
            
            # Step 2: If this step requires looking up in OLD schema
            if lookup_in and lookup_column:
                row_result = self._lookup_in_old_schema(lookup_in, lookup_column, current_value)
                if not row_result:
                    return None
                
                # Extract the specified return column (or use the first non-id column)
                if return_column and return_column in row_result:
                    current_value = row_result[return_column]
                elif 'username' in row_result:
                    current_value = row_result['username']
                else:
                    # Default: use the first non-id column
                    for k, v in row_result.items():
                        if k not in ['id', 'Id', 'ID'] and v:
                            current_value = v
                            break
                
                if not current_value:
                    return None
            
            # Step 3: If this step requires looking up in NEW schema (cached mappings)
            if new_table and new_column:
                if new_table in self.id_mappings and new_column in self.id_mappings[new_table]:
                    resolved_id = self.id_mappings[new_table][new_column].get(current_value)
                    if resolved_id:
                        return resolved_id
                
                # If not cached, try direct DB lookup
                resolved_id = self._lookup_in_new_schema(target_db, new_table, new_column, current_value)
                return resolved_id
        
        return None
    
    def _lookup_in_old_schema(self, table: str, lookup_column: str, lookup_value: Any) -> Optional[Any]:
        """Look up a value in the old schema."""
        try:
            with self.source_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(f"USE `{self.source_db}`")
                cursor.execute(
                    f"SELECT * FROM `{table}` WHERE `{lookup_column}` = %s LIMIT 1",
                    (lookup_value,)
                )
                result = cursor.fetchone()
                if result:
                    # Return the first non-id column value (usually what we need)
                    # Or return the full row for multi-column access
                    return result
        except Exception as e:
            logger.warning(f"FK lookup failed in old schema: {table}.{lookup_column} = {lookup_value}: {e}")
        return None
    
    def _lookup_in_new_schema(
        self,
        target_db: str,
        table: str,
        lookup_column: str,
        lookup_value: Any
    ) -> Optional[int]:
        """Look up an ID in the new schema."""
        try:
            with self.source_conn.cursor() as cursor:
                cursor.execute(f"USE `{target_db}`")
                cursor.execute(
                    f"SELECT `id` FROM `{table}` WHERE `{lookup_column}` = %s LIMIT 1",
                    (lookup_value,)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]
        except Exception as e:
            logger.warning(f"FK lookup failed in new schema: {table}.{lookup_column} = {lookup_value}: {e}")
        return None
