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
    
    def __init__(self, mappings_file: str, source_conn, source_db: str, central_db: str = 'central_database',
                 progress_callback=None):
        """
        Initialize migration executor.
        
        Args:
            mappings_file: Path to field_mappings.json
            source_conn: PyMySQL connection to source database
            source_db: Source database name
            central_db: Central database name
            progress_callback: Optional callback(tables_done, tables_total, current_table)
                               called after each table is migrated.
        """
        self.source_conn = source_conn
        self.source_db = source_db
        self.central_db = central_db
        self.progress_callback = progress_callback
        
        with open(mappings_file, 'r') as f:
            self.mappings = json.load(f)
        
        # Cache for unique constraint detection: {db_name.table_name: [unique_columns]}
        self.unique_constraints_cache: Dict[str, List[List[str]]] = {}

        # Cache for column-existence checks: {"db.table.col" -> bool}
        self._column_exists_cache: Dict[str, bool] = {}
        
        # Universal ID mapping cache: { 'table_name': { 'lookup_column': { old_value: new_id } } }
        self.id_mappings = {}
        
        # Track which tables have been migrated (for dependency resolution)
        self.migrated_tables = set()
        
        # Row-level error tracking: [{table, row_id, error, row_snapshot}, ...]
        self.skipped_rows: List[Dict[str, Any]] = []
    
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
        
        # Step 1: Register site in central DB (needed for FK constraints)
        try:
            self._register_site_in_central(site_info, tenant_db, site_uuid)
        except Exception as e:
            stats['errors'].append({'table': 'site_registry', 'error': str(e)})
            logger.error(f"Failed to register site: {e}")
            return stats
        
        # Step 2: Get migration order (respecting FK dependencies)
        migration_order = self._get_migration_order()

        # Pre-compute the list of tables we'll actually migrate so we know the total
        custom = set(self.mappings.get('_custom_migrations', []))
        tables_to_migrate = [
            t for t in migration_order
            if t in self.mappings and not t.startswith('_') and t not in custom
        ]
        tables_total = len(tables_to_migrate)
        tables_done = 0
        
        # Disable FK checks for the duration of data migration
        # (re-enabled in the finally block below)
        try:
            with self.source_conn.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        except Exception:
            pass  # Best-effort; some connections may not support this

        # Step 3: Migrate each table
        try:
            for old_table in tables_to_migrate:
                tables_done += 1

                # Determine if this table applies to this site
                filters = self._get_site_filters(old_table, site_info)
                if filters is None:
                    logger.debug(f"Skipping {old_table} (not applicable)")
                    if self.progress_callback:
                        self.progress_callback(tables_done, tables_total, old_table)
                    continue  # Skip tables not applicable to this site
                
                logger.info(f"📋 Migrating table: {old_table} ({tables_done}/{tables_total})")
                if self.progress_callback:
                    self.progress_callback(tables_done, tables_total, old_table)
                
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
                        logger.info(f"  ✓ Tenant: {tenant_stats['migrated']} rows")
                    
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
                        logger.info(f"  ✓ Central: {central_stats['migrated']} rows")
                    
                    if tenant_stats['migrated'] == 0 and central_stats['migrated'] == 0:
                        logger.debug(f"  No data to migrate")
                    
                except Exception as e:
                    import traceback
                    error_msg = str(e)
                    traceback_str = traceback.format_exc()
                    stats['errors'].append({'table': old_table, 'error': error_msg})
                    logger.error(f"  ✗ Error migrating {old_table}: {error_msg}")
                    logger.debug(f"Traceback:\n{traceback_str[:500]}")
        finally:
            # Re-enable FK checks regardless of success/failure
            try:
                with self.source_conn.cursor() as cursor:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass
        
        logger.info(f"✅ Migration complete for {username}")
        logger.info(f"Rows migrated: {stats['total_rows']}")
        logger.info(f"Errors: {len(stats['errors'])}")
        
        stats['skipped_rows'] = self.skipped_rows
        return stats
    
    def _register_site_in_central(self, site_info: Dict, tenant_db: str, site_uuid: str):
        """Register site in site_registry (required for FK constraints)."""
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{self.central_db}`")
            cursor.execute("""
                INSERT INTO site_registry (
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
            logger.info(f"Registered in site_registry")
    
    def _get_migration_order(self) -> List[str]:
        """
        Return source tables in the order they should be migrated.

        Default: all non-internal keys from field_mappings.json (keys
        starting with ``_`` are considered internal/meta).

        Override in subclasses to enforce a specific dependency order.
        """
        return [t for t in self.mappings.keys() if not t.startswith('_')]
    
    def _resolve_source_table(self, mapping_key: str) -> str:
        """Map a field_mappings key to the actual source table name.

        Override when the source table has a different name than the
        mapping key. Default: identity (key == table name).
        """
        return mapping_key

    def _get_site_filters(self, old_table: str, site_info: Dict) -> Optional[Dict[str, Any]]:
        """Determine filter criteria for a site-specific table.

        Default implementation looks for ``username`` or ``account_id``
        columns in the source table.  Override in subclasses for more
        complex filter logic (e.g. service-level filtering, column
        aliases, global-row inclusion).

        Returns:
            A filter dict (column → value/list), or ``None`` to skip.
        """
        username = site_info.get('username')
        account_id = site_info.get('id')
        source_table = self._resolve_source_table(old_table)

        try:
            with self.source_conn.cursor(pymysql.cursors.Cursor) as cursor:
                cursor.execute(f"USE `{self.source_db}`")
                cursor.execute(f"SHOW COLUMNS FROM `{source_table}`")
                columns = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.warning(f"Could not check columns for {source_table}: {e}")
            return None

        if 'username' in columns:
            return {'username': username}
        elif 'account_id' in columns:
            return {'account_id': account_id}
        elif 'id_user' in columns:
            return {'id_user': account_id}

        # No recognised filter column — skip in JSON-driven migration
        return None
    
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
    
    def _get_fetch_modifiers(self, old_table: str) -> Dict[str, Any]:
        """Return optional ORDER BY / LIMIT hints for a source table.

        Override in subclasses to cap large tables or control row ordering.

        Returns:
            Dict with optional keys:
            - ``order_by`` (str|None): e.g. ``'id DESC'``
            - ``limit``    (int|None): max rows to fetch
        """
        return {'order_by': None, 'limit': None}

    def _fetch_source_data(self, old_table: str, filters: Optional[Dict]) -> List[Dict]:
        """Fetch source data with filters.

        Filter values can be:
        - scalar  → ``WHERE col = %s``
        - list    → ``WHERE col IN (%s, %s, ...)``  (``None`` in list → ``IS NULL``)

        Applies ORDER BY / LIMIT from ``_get_fetch_modifiers`` when set.
        Uses ``_resolve_source_table`` for the actual table name.
        """
        source_table = self._resolve_source_table(old_table)
        with self.source_conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"USE `{self.source_db}`")
            
            where_clause = ""
            where_params: list = []
            if filters:
                conditions = []
                for k, v in filters.items():
                    if isinstance(v, (list, tuple)):
                        if not v:
                            continue
                        # Separate None (SQL NULL) from real values
                        non_null = [x for x in v if x is not None]
                        has_null = None in v
                        parts = []
                        if non_null:
                            placeholders = ", ".join(["%s"] * len(non_null))
                            parts.append(f"`{k}` IN ({placeholders})")
                            where_params.extend(non_null)
                        if has_null:
                            parts.append(f"`{k}` IS NULL")
                        if parts:
                            conditions.append(f"({' OR '.join(parts)})")
                    else:
                        conditions.append(f"`{k}` = %s")
                        where_params.append(v)
                if conditions:
                    where_clause = " WHERE " + " AND ".join(conditions)
            
            mods = self._get_fetch_modifiers(old_table)
            order_by = mods.get('order_by')
            limit = mods.get('limit')

            query = f"SELECT * FROM `{source_table}`{where_clause}"
            if order_by:
                query += f" ORDER BY {order_by}"
            if limit:
                query += f" LIMIT {int(limit)}"

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
    
    # Override in subclasses to declare FK dependencies between *target*
    # tables.  Format: {dependent_table: [tables_it_depends_on]}.
    # The topological sort in ``_sort_targets_by_dependency`` uses this.
    _TARGET_DEPENDENCIES: Dict[str, List[str]] = {}

    def _sort_targets_by_dependency(self, tables: List[str]) -> List[str]:
        """
        Sort target tables by FK dependency order using ``_TARGET_DEPENDENCIES``.

        Tables without dependencies come first, tables with dependencies
        come later.  Override ``_TARGET_DEPENDENCIES`` in subclasses to
        declare project-specific FK relationships between target tables.
        """
        dependencies = self._TARGET_DEPENDENCIES

        in_migration = set(tables)
        dep_graph = {}
        for table in tables:
            dep_graph[table] = [dep for dep in dependencies.get(table, []) if dep in in_migration]

        # Topological sort
        sorted_tables: List[str] = []
        visited: set = set()
        temp_mark: set = set()

        def visit(table):
            if table in temp_mark:
                return  # circular — just proceed
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
    
    def _has_column(self, cursor, db_name: str, table_name: str, column_name: str) -> bool:
        """Check whether *column_name* exists in *table_name* (cached)."""
        key = f"{db_name}.{table_name}.{column_name}"
        if key not in self._column_exists_cache:
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{db_name}`.`{table_name}` LIKE %s", (column_name,))
                self._column_exists_cache[key] = cursor.fetchone() is not None
            except Exception:
                self._column_exists_cache[key] = False
        return self._column_exists_cache[key]

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
    
    # ────────────────────────────────────────────────────────────
    # FK-source detection: tables whose auto-generated IDs are
    # referenced by downstream lookup_chains.  These MUST be
    # inserted row-by-row so we can capture each lastrowid.
    # ────────────────────────────────────────────────────────────

    _fk_source_cache: Optional[frozenset] = None

    def _get_fk_source_tables(self) -> frozenset:
        """Return the set of target table names that appear in any
        ``lookup_chain[].new_table`` across all mappings.

        These tables need per-row INSERT so their auto-increment IDs
        can be cached for downstream FK resolution.  All other tables
        can safely use batch INSERT.
        """
        if self._fk_source_cache is not None:
            return self._fk_source_cache

        fk_tables: set = set()
        for old_table, field_mappings in self.mappings.items():
            if old_table.startswith('_') or not isinstance(field_mappings, dict):
                continue
            for _field, mapping in field_mappings.items():
                if not isinstance(mapping, dict):
                    continue
                for target in mapping.get('targets', []):
                    for step in (target.get('lookup_chain') or []):
                        nt = step.get('new_table')
                        if nt:
                            fk_tables.add(nt)
        self._fk_source_cache = frozenset(fk_tables)
        return self._fk_source_cache

    # ────────────────────────────────────────────────────────────
    # Prepare a single row's insert_data dict
    # ────────────────────────────────────────────────────────────

    def _prepare_insert_data(
        self,
        row: Dict,
        field_list: List[Dict],
        old_table: str,
        target_table: str,
        target_db: str,
        site_info: Dict,
        site_uuid: str,
        cursor,
    ) -> Optional[Dict]:
        """Build the column→value dict for one source row.

        Returns ``None`` when the row should be skipped (empty data).
        """
        insert_data: Dict[str, Any] = {}

        for field_info in field_list:
            old_field = field_info['old_field']
            new_field = field_info['new_field']
            sql_transform = field_info.get('sql')
            condition = field_info.get('condition')
            lookup_chain = field_info.get('lookup_chain')

            if condition and not self._eval_condition(condition, row):
                continue

            value = self._get_field_value(
                row=row,
                old_field=old_field,
                new_field=new_field,
                sql_transform=sql_transform,
                old_table=old_table,
                target_table=target_table,
                target_db=target_db,
                site_info=site_info,
                lookup_chain=lookup_chain,
            )
            insert_data[new_field] = value

        if not insert_data:
            return None

        # Add site_uuid / site_name when the target table expects them
        if 'site_uuid' not in insert_data:
            if self._has_column(cursor, target_db, target_table, 'site_uuid'):
                insert_data['site_uuid'] = site_uuid

        if 'site_name' not in insert_data or insert_data.get('site_name') is None:
            if self._has_column(cursor, target_db, target_table, 'site_name'):
                site_name_value = site_info.get('siteName', '')
                if site_name_value:
                    insert_data['site_name'] = site_name_value

        return insert_data

    # ────────────────────────────────────────────────────────────
    # Main entry point — chooses batch vs row-by-row
    # ────────────────────────────────────────────────────────────

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
        """Migrate rows to a specific target table.

        Automatically uses **batch INSERT** (via ``executemany``) for
        large tables whose IDs are not referenced by downstream FK
        chains, and falls back to row-by-row INSERT otherwise.
        """
        if not source_rows:
            return 0

        # Phase 1 — prepare every row's insert_data
        prepared: List[Tuple[Dict, Dict]] = []  # (source_row, insert_data)
        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{target_db}`")
            for row in source_rows:
                data = self._prepare_insert_data(
                    row, field_list, old_table, target_table,
                    target_db, site_info, site_uuid, cursor,
                )
                if data is not None:
                    prepared.append((row, data))

        if not prepared:
            return 0

        # Phase 2 — choose strategy
        needs_id_cache = target_table in self._get_fk_source_tables()

        if needs_id_cache or len(prepared) <= 20:
            return self._insert_rows_individually(
                old_table, target_db, target_table, prepared,
            )
        else:
            return self._insert_rows_batch(
                old_table, target_db, target_table, prepared,
            )

    # ────────────────────────────────────────────────────────────
    # Row-by-row INSERT  (original behaviour — needed for FK cache)
    # ────────────────────────────────────────────────────────────

    def _insert_rows_individually(
        self,
        old_table: str,
        target_db: str,
        target_table: str,
        prepared: List[Tuple[Dict, Dict]],
    ) -> int:
        migrated_count = 0
        unique_constraints = self._get_unique_constraints(target_db, target_table)

        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{target_db}`")

            for row, insert_data in prepared:
                try:
                    columns = list(insert_data.keys())
                    placeholders = ["%s"] * len(columns)
                    values = list(insert_data.values())

                    sql = f"""
                        INSERT INTO `{target_table}`
                        ({', '.join(f'`{c}`' for c in columns)})
                        VALUES ({', '.join(placeholders)})
                    """

                    if unique_constraints:
                        update_cols = [c for c in columns if c not in ['id', 'created_at']]
                        if update_cols:
                            sql += " ON DUPLICATE KEY UPDATE "
                            sql += ', '.join(f'`{c}` = VALUES(`{c}`)' for c in update_cols)

                    cursor.execute(sql, values)

                    row_id = cursor.lastrowid
                    if row_id == 0 and unique_constraints:
                        for unique_cols in unique_constraints:
                            if all(col in insert_data for col in unique_cols):
                                wc = ' AND '.join(f'`{col}` = %s' for col in unique_cols)
                                wv = [insert_data[col] for col in unique_cols]
                                cursor.execute(f"SELECT id FROM `{target_table}` WHERE {wc}", wv)
                                result = cursor.fetchone()
                                if result:
                                    row_id = result[0]
                                    break

                    self._cache_id_mapping(old_table, target_table, row, row_id, insert_data)
                    migrated_count += 1

                except Exception as e:
                    rid = row.get('id')
                    logger.warning(f"Skipped row (id={rid}): {str(e)[:100]}")
                    self.skipped_rows.append({
                        'table': old_table,
                        'target_table': target_table,
                        'row_id': rid,
                        'error': str(e)[:300],
                    })

            self.source_conn.commit()

        return migrated_count

    # ────────────────────────────────────────────────────────────
    # Batch INSERT  (fast path for leaf tables with no FK lookups)
    # ────────────────────────────────────────────────────────────

    _BATCH_SIZE = 500

    def _insert_rows_batch(
        self,
        old_table: str,
        target_db: str,
        target_table: str,
        prepared: List[Tuple[Dict, Dict]],
    ) -> int:
        """Multi-value INSERT via ``executemany`` — dramatically reduces
        network round-trips for large tables whose IDs are not consumed
        by downstream FK chains."""
        from collections import defaultdict

        # Group rows by their column signature so each batch has a
        # uniform INSERT statement.
        groups: Dict[Tuple[str, ...], List[Tuple[Dict, Dict]]] = defaultdict(list)
        for source_row, insert_data in prepared:
            col_key = tuple(sorted(insert_data.keys()))
            groups[col_key].append((source_row, insert_data))

        unique_constraints = self._get_unique_constraints(target_db, target_table)
        migrated_count = 0
        total_rows = len(prepared)

        with self.source_conn.cursor() as cursor:
            cursor.execute(f"USE `{target_db}`")

            for col_key, rows_in_group in groups.items():
                columns = list(col_key)

                sql = (
                    f"INSERT INTO `{target_table}` "
                    f"({', '.join(f'`{c}`' for c in columns)}) "
                    f"VALUES ({', '.join(['%s'] * len(columns))})"
                )

                if unique_constraints:
                    update_cols = [c for c in columns if c not in ['id', 'created_at']]
                    if update_cols:
                        sql += " ON DUPLICATE KEY UPDATE "
                        sql += ', '.join(f'`{c}` = VALUES(`{c}`)' for c in update_cols)

                # Build value tuples
                value_tuples = [
                    tuple(data[col] for col in columns)
                    for _row, data in rows_in_group
                ]

                # Execute in chunks
                for i in range(0, len(value_tuples), self._BATCH_SIZE):
                    chunk = value_tuples[i : i + self._BATCH_SIZE]
                    chunk_rows = rows_in_group[i : i + self._BATCH_SIZE]
                    try:
                        cursor.executemany(sql, chunk)
                        migrated_count += len(chunk)
                    except Exception as batch_err:
                        # Fallback: row-by-row for this chunk so we can
                        # identify and skip individual bad rows.
                        logger.warning(
                            f"Batch insert failed for {target_table} "
                            f"(chunk {i}–{i+len(chunk)}), falling back "
                            f"to row-by-row: {batch_err}"
                        )
                        for source_row, insert_data in chunk_rows:
                            try:
                                vals = tuple(insert_data[col] for col in columns)
                                cursor.execute(sql, vals)
                                migrated_count += 1
                            except Exception as row_err:
                                rid = source_row.get('id')
                                logger.warning(f"Skipped row (id={rid}): {str(row_err)[:100]}")
                                self.skipped_rows.append({
                                    'table': old_table,
                                    'target_table': target_table,
                                    'row_id': rid,
                                    'error': str(row_err)[:300],
                                })

                    # Log progress for large tables
                    if total_rows > 100 and migrated_count > 0:
                        logger.info(
                            f"  … {target_table}: {migrated_count}/{total_rows} rows"
                        )

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
        # 1. Check if this field requires FK chain resolution
        if lookup_chain and isinstance(lookup_chain, list):
            resolved_id = self._resolve_fk_chain(row, lookup_chain, target_db)
            if resolved_id is not None:
                return resolved_id
            else:
                # When FK resolution fails, return None (field should be nullable)
                return None
        
        # 2. Get base value from source row
        base_value = row.get(old_field)
        
        # 3. Universal FK resolution: Check if we have a cached mapping
        if new_field == 'user_id':
            # Try to resolve from cached mappings
            if 'user' in self.id_mappings and 'username' in self.id_mappings['user']:
                username = row.get('username', base_value)
                if username and username in self.id_mappings['user']['username']:
                    return self.id_mappings['user']['username'][username]
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
        
        # Cache any legacy_* columns (used for FK resolution across schemas)
        for col, val in inserted_data.items():
            if col.startswith('legacy_') and val is not None:
                unique_columns_to_cache.append((col, val))
        
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
            {'old_table': 'patients', 'old_column': 'username', 'new_table': 'user', 'new_column': 'username'}
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
            
            # Step 1: Get value from current context
            if step_idx == 0:
                # First step: get value from source_row
                current_value = source_row.get(old_column)
                if not current_value:
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
            # Explicitly use plain Cursor (not DictCursor) so result[0] works
            with self.source_conn.cursor(pymysql.cursors.Cursor) as cursor:
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
