#!/usr/bin/env python3
"""
Build Schema Diagram

Parses SQL schema files + field_mappings.json to generate a complete HTML visualization.
Shows migration targets and SQL for each field.

Usage:
    python scripts/build_diagram.py
"""

import re
import json
import os

def parse_sql_schema(sql_content, schema_name):
    """Parse CREATE TABLE statements from SQL."""
    tables = {}
    all_fk_relations = []  # Store FK relationships
    
    # Split by CREATE TABLE to handle each table separately
    # This is more reliable than trying to match the entire CREATE TABLE in one regex
    parts = re.split(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?', sql_content, flags=re.IGNORECASE)
    
    for part in parts[1:]:  # Skip first empty part
        # Get table name
        name_match = re.match(r'[`"]?(\w+)[`"]?\s*\(', part)
        if not name_match:
            continue
        table_name = name_match.group(1)
        
        # Find the matching closing parenthesis for CREATE TABLE
        # Count parentheses to find the right one
        start_idx = part.find('(')
        if start_idx == -1:
            continue
        
        depth = 0
        end_idx = start_idx
        for i, char in enumerate(part[start_idx:], start_idx):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        
        body = part[start_idx+1:end_idx]
        
        columns = []
        constraints = {'pk': [], 'fk': [], 'uk': []}
        fk_references = {}  # col -> (ref_table, ref_col)
        
        # Split by lines and parse each
        for line in body.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Remove trailing comma
            line = line.rstrip(',')
            
            upper = line.upper()
            
            # Handle PRIMARY KEY constraint
            if upper.startswith('PRIMARY KEY'):
                pk_match = re.search(r'\(([^)]+)\)', line)
                if pk_match:
                    constraints['pk'] = [c.strip().strip('`"') for c in pk_match.group(1).split(',')]
                continue
            
            # Handle UNIQUE KEY constraint
            if upper.startswith('UNIQUE KEY') or upper.startswith('UNIQUE INDEX') or upper.startswith('UNIQUE ('):
                uk_match = re.search(r'\(([^)]+)\)', line)
                if uk_match:
                    for c in uk_match.group(1).split(','):
                        col = c.strip().strip('`"').split('(')[0]  # Handle key length like varchar(255)
                        if col and col not in constraints['uk']:
                            constraints['uk'].append(col)
                continue
            
            # Handle KEY/INDEX
            if upper.startswith('KEY ') or upper.startswith('INDEX '):
                continue
            
            # Handle FOREIGN KEY - capture the reference
            if upper.startswith('FOREIGN KEY'):
                fk_match = re.search(
                    r'FOREIGN KEY\s*\([`"]?(\w+)[`"]?\)\s*REFERENCES\s*[`"]?(\w+)[`"]?\s*\([`"]?(\w+)[`"]?\)',
                    line, re.IGNORECASE
                )
                if fk_match:
                    fk_col = fk_match.group(1)
                    ref_table = fk_match.group(2)
                    ref_col = fk_match.group(3)
                    constraints['fk'].append(fk_col)
                    fk_references[fk_col] = (ref_table, ref_col)
                    all_fk_relations.append({
                        'from_table': table_name,
                        'from_col': fk_col,
                        'to_table': ref_table,
                        'to_col': ref_col
                    })
                continue
            
            # Handle CONSTRAINT
            if upper.startswith('CONSTRAINT'):
                # Also check for FK in CONSTRAINT lines
                fk_match = re.search(
                    r'FOREIGN KEY\s*\([`"]?(\w+)[`"]?\)\s*REFERENCES\s*[`"]?(\w+)[`"]?\s*\([`"]?(\w+)[`"]?\)',
                    line, re.IGNORECASE
                )
                if fk_match:
                    fk_col = fk_match.group(1)
                    ref_table = fk_match.group(2)
                    ref_col = fk_match.group(3)
                    constraints['fk'].append(fk_col)
                    fk_references[fk_col] = (ref_table, ref_col)
                    all_fk_relations.append({
                        'from_table': table_name,
                        'from_col': fk_col,
                        'to_table': ref_table,
                        'to_col': ref_col
                    })
                continue
            
            # Handle other non-column lines
            if upper.startswith(('CHECK', 'FULLTEXT', 'SPATIAL')):
                continue
            
            # Parse column definition
            # Match: `column_name` type...
            col_match = re.match(r'[`"]?(\w+)[`"]?\s+(\w+(?:\([^)]+\))?(?:\s+UNSIGNED)?)', line, re.IGNORECASE)
            if col_match:
                col_name = col_match.group(1)
                col_type = col_match.group(2).lower()
                
                # Check for inline PRIMARY KEY
                is_pk = 'PRIMARY KEY' in upper and 'PRIMARY KEY (' not in upper
                is_uk = ' UNIQUE' in upper and 'UNIQUE KEY' not in upper and 'UNIQUE INDEX' not in upper
                is_auto = 'AUTO_INCREMENT' in upper
                
                # Extract source comment if present
                source = None
                source_match = re.search(r"COMMENT\s+'Source:\s*([^']+)'", line, re.IGNORECASE)
                if source_match:
                    source = source_match.group(1).strip()
                
                columns.append({
                    'name': col_name,
                    'type': col_type,
                    'pk': is_pk,
                    'uk': is_uk,
                    'fk': False,
                    'fk_ref': None,
                    'auto': is_auto,
                    'source': source
                })
        
        # Apply constraints to columns
        for col in columns:
            if col['name'] in constraints['pk']:
                col['pk'] = True
            if col['name'] in constraints['uk']:
                col['uk'] = True
            if col['name'] in constraints['fk']:
                col['fk'] = True
                if col['name'] in fk_references:
                    col['fk_ref'] = fk_references[col['name']]
        
        category = categorize_table(table_name, schema_name)
        tables[table_name] = {'columns': columns, 'category': category, 'schema': schema_name}
    
    return tables, all_fk_relations


def categorize_table(table_name, schema_name):
    name = table_name.lower()
    if schema_name == 'central':
        return 'central'
    if name in ('sysadmin_systemsettings', 'account_info', 'sysadmin_services'):
        return 'core'
    elif name in ('series', 'report_data', 'report_file', 'dicom_tags', 'magnets', 'dicom_dictionary'):
        return 'imaging'
    elif 'config' in name or 'option' in name or 'routing' in name or 'rsi' in name:
        return 'config'
    elif 'job' in name or 'container' in name or 'upload' in name or 'task' in name:
        return 'jobs'
    elif 'license' in name or 'ms365' in name or 'session' in name:
        return 'auth'
    elif 'audit' in name or 'devlog' in name or 'log' in name:
        return 'logging'
    elif 'metric' in name or 'trend' in name or 'activity' in name:
        return 'metrics'
    elif 'status' in name or 'mapping' in name or 'qcscore' in name or 'dictionary' in name:
        return 'lookup'
    elif name.startswith('test') or 'reference' in name or 'structure' in name or 'protocol' in name:
        return 'legacy'
    elif name in ('site', 'users'):
        return 'core'
    elif name in ('patients', 'studies'):
        return 'imaging'
    elif 'processing' in name:
        return 'jobs'
    return 'core'


def merge_mappings(old_tables, mappings, deprecated_tables):
    """Add migration target and SQL info to old schema columns. Supports multi-target mappings."""
    for table_name, table_data in old_tables.items():
        table_mappings = mappings.get(table_name, {})
        
        # Check if entire table is deprecated
        if table_name in deprecated_tables:
            for col in table_data['columns']:
                col['target'] = None
                col['targets'] = []
                col['deprecated'] = True
                col['reason'] = deprecated_tables[table_name]
                col['sql'] = None
            continue
        
        for col in table_data['columns']:
            col_mapping = table_mappings.get(col['name'], {})
            
            # Handle new multi-target format
            if 'targets' in col_mapping:
                col['targets'] = col_mapping['targets']
                # For backward compatibility, set 'target' to first target's full path
                if col_mapping['targets']:
                    first_target = col_mapping['targets'][0]
                    col['target'] = f"{first_target.get('table', '')}.{first_target.get('column', '')}"
                else:
                    col['target'] = None
                col['sql'] = '; '.join(t.get('sql', '') for t in col_mapping['targets'] if t.get('sql'))
            # Handle old single-target format (backward compatible)
            elif 'target' in col_mapping:
                col['target'] = col_mapping.get('target')
                col['targets'] = []
                col['sql'] = col_mapping.get('sql')
            else:
                col['target'] = None
                col['targets'] = []
                col['sql'] = None
            
            col['deprecated'] = col_mapping.get('deprecated', False)
            col['reason'] = col_mapping.get('reason')
            
            # If no mapping defined at all, mark as needing review
            if not col['target'] and not col['targets'] and not col['deprecated'] and table_name not in deprecated_tables:
                if table_mappings:  # Table has some mappings but this column doesn't
                    col['deprecated'] = True
                    col['reason'] = 'No mapping defined - review needed'
    
    return old_tables


def generate_html(old_tables, new_tables, central_tables, old_fk_relations, new_fk_relations, central_fk_relations):
    """Generate the complete HTML file."""
    
    all_data = {
        'old': old_tables,
        'new': new_tables,
        'central': central_tables
    }
    
    all_fk = {
        'old': old_fk_relations,
        'new': new_fk_relations,
        'central': central_fk_relations
    }
    
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CTX Schema Migration - Complete</title>
    <style>
        :root {
            --bg: #0d1117; --card: #161b22; --border: #30363d;
            --text: #e6edf3; --dim: #8b949e; --blue: #58a6ff;
            --green: #3fb950; --yellow: #d29922; --red: #f85149;
            --purple: #a371f7; --cyan: #39c5cf; --orange: #db6d28;
            /* Category colors */
            --core: #58a6ff; --imaging: #3fb950; --config: #f85149;
            --jobs: #a371f7; --auth: #db61a2; --logging: #db6d28;
            --metrics: #39c5cf; --lookup: #d29922; --legacy: #6e7681;
            --central: #f0883e;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); font-size: 13px; height: 100vh; overflow: hidden; }
        
        .header { height: 50px; background: var(--card); border-bottom: 1px solid var(--border); padding: 0 20px; display: flex; align-items: center; gap: 16px; }
        .header h1 { font-size: 15px; font-weight: 600; }
        .tabs { display: flex; gap: 4px; background: var(--bg); padding: 4px; border-radius: 8px; align-items: center; }
        .tab { padding: 6px 14px; border: none; border-radius: 6px; background: transparent; color: var(--dim); cursor: pointer; font-size: 12px; font-weight: 500; }
        .tab:hover { color: var(--text); }
        .tab.active { background: var(--blue); color: white; }
        .reset-btn { margin-left: auto; padding: 6px 12px; border: 1px solid var(--dim); border-radius: 6px; background: transparent; color: var(--dim); cursor: pointer; font-size: 11px; font-weight: 500; transition: all 0.2s; }
        .reset-btn:hover { border-color: var(--purple); color: var(--purple); background: rgba(163, 113, 247, 0.1); }
        .node { transition: opacity 0.2s; }
        .node.dragging { opacity: 0.7; cursor: grabbing !important; }
        .legend { display: flex; gap: 10px; margin-left: auto; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--dim); }
        .legend-dot { width: 8px; height: 8px; border-radius: 2px; }
        .stats { font-size: 11px; color: var(--dim); margin-left: 10px; }
        
        .main { display: flex; height: calc(100vh - 50px); }
        .graph-panel { flex: 1; overflow: auto; padding: 20px; }
        
        /* 3-Column Comparison Table */
        .comparison-table { width: 100%; border-collapse: collapse; font-size: 10px; margin-top: 10px; table-layout: fixed; }
        .comparison-table th { background: var(--hover); padding: 6px 8px; text-align: left; font-weight: 600; border-bottom: 2px solid var(--border); position: sticky; top: 0; z-index: 10; word-wrap: break-word; }
        .comparison-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; word-wrap: break-word; overflow-wrap: break-word; }
        .comparison-table tr:hover { background: var(--hover); }
        .comparison-table .col-name { font-family: 'Courier New', monospace; font-weight: 500; color: var(--blue); word-break: break-word; }
        .comparison-table .col-type { color: var(--dim); font-size: 9px; margin-left: 5px; display: block; margin-top: 2px; }
        .comparison-table .col-badges { display: flex; gap: 3px; margin-top: 2px; flex-wrap: wrap; }
        .comparison-table .badge { padding: 1px 4px; border-radius: 2px; font-size: 8px; font-weight: 600; white-space: nowrap; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
        .comparison-table .badge:hover { transform: scale(1.1); box-shadow: 0 0 6px rgba(255,255,255,0.3); }
        .comparison-table .badge.pk { background: var(--blue); color: white; }
        .comparison-table .badge.fk { background: var(--purple); color: white; }
        .comparison-table .badge.uk { background: var(--orange); color: white; }
        .comparison-table .missing { color: var(--dim); font-style: italic; }
        .comparison-table .deprecated { background: var(--bg); opacity: 0.6; }
        
        /* Column widths - 3 columns (old schema view) */
        .comparison-table .schema-col { width: 23%; }
        .comparison-table .schema-col.old-schema { width: 31%; }
        
        /* Column widths - 2 columns (new/central view) - wider columns */
        .comparison-table.two-column .schema-col { width: 50%; }
        
        /* Responsive - hide New/Central columns on small screens */
        @media (max-width: 1200px) {
            .comparison-table .schema-col.new-schema,
            .comparison-table .schema-col.central-schema {
                display: none;
            }
            .comparison-table .schema-col { width: 100%; }
            .comparison-table.two-column .schema-col { width: 100%; }
            .hide-on-small { display: none; }
        }
        
        /* FK Arrow Tooltip */
        .fk-tooltip { position: absolute; background: var(--card); border: 1px solid var(--border); padding: 8px 10px; border-radius: 4px; font-size: 10px; pointer-events: none; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.2); max-width: 250px; }
        .fk-tooltip .tooltip-title { font-weight: 600; color: var(--purple); margin-bottom: 4px; }
        .fk-tooltip .tooltip-row { margin: 2px 0; color: var(--text); }
        .fk-tooltip .tooltip-label { color: var(--dim); font-size: 9px; }
        
        /* FK Arrow Hover Effects */
        .fk-line { transition: stroke 0.2s, stroke-width 0.2s, filter 0.2s; }
        .fk-line.hovered { 
            stroke: #ffffff !important; 
            stroke-width: 2.5 !important; 
            stroke-opacity: 1 !important;
            filter: drop-shadow(0 0 8px rgba(163,113,247,0.8)) drop-shadow(0 0 4px rgba(255,255,255,0.6));
            animation: fk-glow 1.5s ease-in-out infinite;
        }
        @keyframes fk-glow {
            0%, 100% { filter: drop-shadow(0 0 6px rgba(163,113,247,0.8)) drop-shadow(0 0 3px rgba(255,255,255,0.6)); }
            50% { filter: drop-shadow(0 0 12px rgba(163,113,247,1)) drop-shadow(0 0 6px rgba(255,255,255,0.8)); }
        }
        
        .node { cursor: pointer; transition: all 0.2s; }
        .node-bg { fill: var(--card); stroke-width: 1.5; rx: 6; transition: fill 0.15s, stroke-width 0.15s, filter 0.15s; }
        .node:hover .node-bg { fill: #1c2128; stroke-width: 2; }
        .node.selected .node-bg { stroke-width: 2.5; filter: drop-shadow(0 0 8px rgba(88,166,255,0.3)); }
        .node.fk-connected .node-bg { 
            stroke-width: 3 !important; 
            filter: drop-shadow(0 0 10px rgba(163,113,247,0.6));
        }
        .node-stripe { rx: 3; }
        .node-text { font-size: 9px; font-weight: 500; fill: var(--text); pointer-events: none; }
        .node-count { font-size: 8px; fill: var(--dim); pointer-events: none; }
        
        .c-core { fill: #58a6ff; } .stroke-core { stroke: #58a6ff; }
        .c-imaging { fill: #3fb950; } .stroke-imaging { stroke: #3fb950; }
        .c-config { fill: #f85149; } .stroke-config { stroke: #f85149; }
        .c-jobs { fill: #a371f7; } .stroke-jobs { stroke: #a371f7; }
        .c-auth { fill: #db61a2; } .stroke-auth { stroke: #db61a2; }
        .c-logging { fill: #db6d28; } .stroke-logging { stroke: #db6d28; }
        .c-metrics { fill: #39c5cf; } .stroke-metrics { stroke: #39c5cf; }
        .c-lookup { fill: #d29922; } .stroke-lookup { stroke: #d29922; }
        .c-legacy { fill: #6e7681; } .stroke-legacy { stroke: #6e7681; }
        .c-central { fill: #f0883e; } .stroke-central { stroke: #f0883e; }
        
        .fk-line { pointer-events: none; transition: stroke-opacity 0.2s, stroke-width 0.2s; }
        
        .detail-panel { width: 864px; background: var(--card); border-left: 1px solid var(--border); display: flex; flex-direction: column; }
        .detail-panel.collapsed { width: 0; overflow: hidden; border-left: none; }
        
        /* Responsive: smaller panel on small screens */
        @media (max-width: 1400px) {
            .detail-panel { width: 480px; }
        }
        .detail-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
        .detail-title { font-size: 14px; font-weight: 600; }
        .badge { font-size: 9px; padding: 2px 8px; border-radius: 10px; font-weight: 500; color: white; }
        .close-btn { margin-left: auto; width: 24px; height: 24px; border: none; border-radius: 6px; background: transparent; color: var(--dim); cursor: pointer; font-size: 16px; }
        .close-btn:hover { background: var(--bg); color: var(--text); }
        
        .cols-list { flex: 1; overflow-y: auto; max-height: 75vh; }
        .col-item { padding: 6px 14px; border-bottom: 1px solid var(--border); cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 11px; }
        .col-item:hover { background: rgba(88,166,255,0.08); }
        .col-item.mapped { background: rgba(63,185,80,0.04); }
        .col-item.deprecated { background: rgba(248,81,73,0.04); opacity: 0.7; }
        .col-item.selected { background: rgba(88,166,255,0.15); }
        .col-name { font-weight: 500; flex: 1; }
        .col-type { font-family: 'SF Mono', Monaco, monospace; font-size: 9px; color: var(--blue); }
        .col-arrow { color: var(--green); font-size: 10px; }
        .col-x { color: var(--red); font-size: 10px; }
        .key-badge { font-size: 7px; padding: 1px 3px; border-radius: 2px; font-weight: 700; }
        .key-pk { background: var(--yellow); color: #000; }
        .key-fk { background: var(--purple); color: #fff; }
        .key-uk { background: var(--cyan); color: #000; }
        
        .migration-panel { flex-shrink: 0; max-height: 20vh; overflow-y: auto; background: var(--bg); padding: 10px; }
        .migration-title { font-size: 10px; font-weight: 600; color: var(--green); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        .lineage-box { background: var(--card); border-radius: 6px; padding: 10px; margin-bottom: 6px; border-left: 3px solid var(--border); }
        .lineage-box.source { border-left-color: var(--orange); }
        .lineage-box.target { border-left-color: var(--green); }
        .lineage-box.deprecated { border-left-color: var(--red); }
        .lineage-box.clickable { cursor: pointer; transition: background 0.15s, transform 0.1s; }
        .lineage-box.clickable:hover { background: #1c2128; transform: translateX(3px); }
        .lineage-label { font-size: 8px; text-transform: uppercase; color: var(--dim); margin-bottom: 2px; letter-spacing: 0.3px; }
        .lineage-value { font-family: monospace; font-size: 11px; color: var(--blue); }
        .lineage-arrow { text-align: center; color: var(--green); font-size: 12px; padding: 2px; }
        .reason { font-size: 10px; color: var(--red); margin-top: 4px; font-style: italic; }
        .sql-box { background: #1a1f29; border: 1px solid var(--border); border-radius: 4px; padding: 8px; margin-top: 8px; font-family: 'SF Mono', Monaco, monospace; font-size: 9px; color: var(--cyan); white-space: pre-wrap; word-break: break-all; max-height: 100px; overflow-y: auto; }
        .sql-label { font-size: 8px; color: var(--dim); margin-bottom: 4px; text-transform: uppercase; }
        .empty-state { padding: 20px; text-align: center; color: var(--dim); }
        .empty-state h4 { color: var(--text); margin-bottom: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 CTX Schema Migration</h1>
        <div class="tabs">
            <button class="tab active" data-view="old">Old Schema</button>
            <button class="tab" data-view="new">New Tenant</button>
            <button class="tab" data-view="central">Central</button>
            <button class="reset-btn" onclick="resetPositions()" title="Reset table positions to default layout">🔄 Reset Layout</button>
        </div>
        <div class="stats" id="stats"></div>
        <div class="legend" id="legend"></div>
    </div>
    
    <div class="main">
        <div class="graph-panel" id="graphPanel"></div>
        <div class="detail-panel collapsed" id="detailPanel">
            <div class="detail-header">
                <div class="detail-title" id="detailTitle">Table</div>
                <div class="badge" id="detailBadge">Category</div>
                <button class="close-btn" onclick="closePanel()">×</button>
            </div>
            <div class="cols-list" id="colsList"></div>
            <div class="migration-panel" id="migrationPanel">
                <div class="empty-state"><h4>Select a column</h4><p>Click any column for migration details</p></div>
            </div>
        </div>
    </div>

<script>
const schemaData = ''' + json.dumps(all_data, indent=2) + ''';

const fkRelations = ''' + json.dumps(all_fk, indent=2) + ''';

const categories = {
    core: { name: 'Core', color: 'core' },
    imaging: { name: 'Imaging', color: 'imaging' },
    config: { name: 'Config', color: 'config' },
    jobs: { name: 'Jobs', color: 'jobs' },
    auth: { name: 'Auth', color: 'auth' },
    logging: { name: 'Logging', color: 'logging' },
    metrics: { name: 'Metrics', color: 'metrics' },
    lookup: { name: 'Lookup', color: 'lookup' },
    legacy: { name: 'Legacy', color: 'legacy' },
    central: { name: 'Central', color: 'central' }
};

let currentView = 'old';
let selectedTable = null;
let isDragging = false;
let draggedTable = null;
let dragOffset = { x: 0, y: 0 };
let isDraggingArrow = false;
let draggedArrowId = null;
let customArrowPaths = {}; // Store custom arrow paths
let mouseDownPos = null; // Track where mouse was pressed
let hasMoved = false; // Track if mouse has moved

function getSchema() { return schemaData[currentView] || {}; }

function loadSavedPositions() {
    try {
        const saved = localStorage.getItem(`schema-positions-${currentView}`);
        return saved ? JSON.parse(saved) : {};
    } catch (e) {
        console.error('Failed to load saved positions:', e);
        return {};
    }
}

function savePositions(positions) {
    try {
        localStorage.setItem(`schema-positions-${currentView}`, JSON.stringify(positions));
    } catch (e) {
        console.error('Failed to save positions:', e);
    }
}

function resetPositions() {
    if (confirm('Reset all table positions to default layout?')) {
        localStorage.removeItem(`schema-positions-${currentView}`);
        renderGraph();
    }
}

function layoutTables(tables) {
    const relations = fkRelations[currentView] || [];
    
    // Count connections per table
    const connectionCount = {};
    Object.keys(tables).forEach(t => connectionCount[t] = 0);
    relations.forEach(rel => {
        connectionCount[rel.from_table] = (connectionCount[rel.from_table] || 0) + 1;
        connectionCount[rel.to_table] = (connectionCount[rel.to_table] || 0) + 1;
    });
    
    // Separate tables into CONNECTED (has FK) and ISOLATED (no FK)
    const connectedTables = [];
    const isolatedTables = [];
    
    Object.keys(tables).forEach(name => {
        if (connectionCount[name] > 0) {
            connectedTables.push(name);
        } else {
            isolatedTables.push(name);
        }
    });
    
    // Sort connected tables by connection count (most connected first for spiral)
    connectedTables.sort((a, b) => (connectionCount[b] || 0) - (connectionCount[a] || 0));
    
    const positions = {};
    const getWidth = (name) => Math.max(95, Math.min(200, name.length * 7 + 20));
    
    // SPIRAL LAYOUT - ONLY for connected tables (those with FK relationships)
    const centerX = 800; // Center of canvas
    const centerY = 350; // Center of canvas (higher since we have rows below)
    const boxHeight = 55; // Height including padding
    const minSpacing = 35; // Minimum space between boxes
    
    if (connectedTables.length > 0) {
        // Start with most connected table at center
        const firstTable = connectedTables[0];
        const firstW = getWidth(firstTable);
        positions[firstTable] = { x: centerX - firstW / 2, y: centerY, w: firstW };
    }
    
    // Helper function to check if a position overlaps with existing boxes
    const checkOverlap = (x, y, w) => {
        for (const [name, pos] of Object.entries(positions)) {
            const dx = Math.abs((x + w/2) - (pos.x + pos.w/2));
            const dy = Math.abs((y + boxHeight/2) - (pos.y + boxHeight/2));
            const minDx = (w + pos.w)/2 + minSpacing;
            const minDy = boxHeight + minSpacing;
            
            if (dx < minDx && dy < minDy) {
                return true; // Overlap detected
            }
        }
        return false;
    };
    
    // Spiral parameters
    let angle = 0; // Start angle
    let radius = 150; // Initial radius from center (larger to avoid overlap with center)
    const radiusGrowth = 0.5; // How much radius grows per angle increment (smooth spiral)
    const angleIncrement = Math.PI / 6; // 30 degrees per step (12 positions per full circle)
    
    // Place remaining CONNECTED tables in spiral
    for (let i = 1; i < connectedTables.length; i++) {
        const tableName = connectedTables[i];
        const w = getWidth(tableName);
        
        let placed = false;
        let attempts = 0;
        const maxAttempts = 100;
        
        // Try to place the box, moving outward in spiral until no overlap
        while (!placed && attempts < maxAttempts) {
            const x = centerX + radius * Math.cos(angle) - w / 2;
            const y = centerY + radius * Math.sin(angle);
            
            if (!checkOverlap(x, y, w)) {
                positions[tableName] = { x, y, w };
                placed = true;
            } else {
                // Move to next position in spiral
                angle += angleIncrement;
                radius += radiusGrowth;
            }
            
            attempts++;
        }
        
        // If still not placed after max attempts, force place it further out
        if (!placed) {
            const x = centerX + radius * Math.cos(angle) - w / 2;
            const y = centerY + radius * Math.sin(angle);
            positions[tableName] = { x, y, w };
        }
        
        // Continue spiral for next box
        angle += angleIncrement;
        radius += radiusGrowth;
    }
    
    // TRADITIONAL COLUMN LAYOUT - for ISOLATED tables (no FK relationships)
    // Group by category and arrange in COMPACT columns on the RIGHT side
    if (isolatedTables.length > 0) {
        // Group isolated tables by category
        const isolatedByCategory = {};
        isolatedTables.forEach(name => {
            const cat = tables[name].category || 'core';
            if (!isolatedByCategory[cat]) isolatedByCategory[cat] = [];
            isolatedByCategory[cat].push(name);
        });
        
        // Arrange in COMPACT columns on RIGHT side (better use of horizontal space!)
        const columnStartX = 1300; // Start from right side
        const hGap = 20; // Horizontal gap between columns
        const vGap = 15; // TIGHT vertical spacing (no arrows needed!)
        let currentX = columnStartX;
        const maxColumnHeight = 900; // Max height per column before starting new column
        
        const catOrder = ['core', 'auth', 'config', 'imaging', 'jobs', 'logging', 'metrics', 'lookup', 'legacy', 'central'];
        
        let currentY = 100; // Start from top
        
        catOrder.forEach(cat => {
            if (!isolatedByCategory[cat] || isolatedByCategory[cat].length === 0) return;
            
            const tablesInCat = isolatedByCategory[cat];
            
            // Place tables vertically in current column
            tablesInCat.forEach(name => {
                const w = getWidth(name);
                
                // Check if we need to start a new column (height exceeded)
                if (currentY + boxHeight > maxColumnHeight) {
                    currentX += 220; // Move to next column (max box width ~200 + gap)
                    currentY = 100; // Reset to top
                }
                
                // Check for overlap with existing tables
                let x = currentX;
                let y = currentY;
                let attempts = 0;
                
                while (attempts < 10) {
                    let hasOverlap = false;
                    for (const [existingName, existingPos] of Object.entries(positions)) {
                        const dx = Math.abs((x + w/2) - (existingPos.x + existingPos.w/2));
                        const dy = Math.abs((y + boxHeight/2) - (existingPos.y + boxHeight/2));
                        if (dx < (w + existingPos.w)/2 + 10 && dy < boxHeight + 10) {
                            hasOverlap = true;
                            break;
                        }
                    }
                    
                    if (!hasOverlap) {
                        positions[name] = { x, y, w };
                        break;
                    }
                    
                    // Overlap detected, shift down
                    y += 10;
                    attempts++;
                }
                
                // Force place if couldn't find spot
                if (!positions[name]) {
                    positions[name] = { x, y: currentY, w };
                }
                
                currentY += boxHeight + vGap;
            });
            
            // Small gap between categories
            currentY += 10;
        });
    }
    
    // Merge with saved positions (overrides default layout)
    const savedPositions = loadSavedPositions();
    Object.keys(savedPositions).forEach(name => {
        if (positions[name]) {
            positions[name] = { ...positions[name], ...savedPositions[name] };
        }
    });
    
    return positions;
}

function renderLegend() {
    const schema = getSchema();
    const usedCats = [...new Set(Object.values(schema).map(t => t.category))];
    document.getElementById('legend').innerHTML = usedCats.map(cat => 
        `<div class="legend-item"><div class="legend-dot" style="background:var(--${categories[cat]?.color || 'dim'})"></div>${categories[cat]?.name || cat}</div>`
    ).join('');
    
    const tableCount = Object.keys(schema).length;
    const colCount = Object.values(schema).reduce((sum, t) => sum + (t.columns?.length || 0), 0);
    document.getElementById('stats').textContent = `${tableCount} tables • ${colCount} columns`;
}

function renderGraph() {
    const schema = getSchema();
    const positions = layoutTables(schema);
    const relations = fkRelations[currentView] || [];
    
    let maxX = 0, maxY = 0, minY = 9999;
    Object.values(positions).forEach(p => { 
        maxX = Math.max(maxX, p.x + p.w + 100);
        maxY = Math.max(maxY, p.y + 150);
        minY = Math.min(minY, p.y);
    });
    
    // Ensure we have LOTS of space for arrows that route around
    maxY += 200; // Extra space at bottom for routing
    const canvasHeight = Math.max(maxY, 1200); // Minimum height = 1200px (was 1000px)
    const canvasWidth = Math.max(maxX + 100, 2200); // Wider canvas for right-side tables
    
    let svg = `<svg width="${canvasWidth}" height="${canvasHeight}" style="min-width:100%">`;
    
    // Define markers for relationship cardinality
    svg += `<defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#a371f7"/>
        </marker>
        <marker id="one-mark" markerWidth="10" markerHeight="10" refX="5" refY="5">
            <line x1="5" y1="2" x2="5" y2="8" stroke="#a371f7" stroke-width="2"/>
        </marker>
        <marker id="many-mark" markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">
            <path d="M 0,2 L 7,5 L 0,8" fill="none" stroke="#a371f7" stroke-width="1.5"/>
        </marker>
    </defs>`;
    
    // Group relationships by table pairs to detect overlaps
    const relationsByPair = {};
    relations.forEach(rel => {
        const key = `${rel.from_table}->${rel.to_table}`;
        if (!relationsByPair[key]) relationsByPair[key] = [];
        relationsByPair[key].push(rel);
    });
    
    // Draw FK arrows with orthogonal routing
    relations.forEach((rel, idx) => {
        const fromPos = positions[rel.from_table];
        const toPos = positions[rel.to_table];
        if (!fromPos || !toPos) return;
        
        // Get column details for FK
        const fromTable = schema[rel.from_table];
        const toTable = schema[rel.to_table];
        const fromCol = fromTable?.columns?.find(c => c.name === rel.from_col);
        const toCol = toTable?.columns?.find(c => c.name === rel.to_col);
        
        const fromType = fromCol?.type || 'unknown';
        const toType = toCol?.type || 'unknown';
        const relationshipType = 'N:1'; // FK is typically many-to-one
        
        // Determine offset based on relationships between same tables
        const pairKey = `${rel.from_table}->${rel.to_table}`;
        const pairRels = relationsByPair[pairKey];
        const relIndexInPair = pairRels.indexOf(rel);
        const totalInPair = pairRels.length;
        
        // Calculate centers of both boxes
        const fromCenterX = fromPos.x + fromPos.w / 2;
        const fromCenterY = fromPos.y + 22.5; // Middle of 45px height
        const toCenterX = toPos.x + toPos.w / 2;
        const toCenterY = toPos.y + 22.5;
        
        // Determine best exit/entry points based on relative positions
        let fromX, fromY, toX, toY;
        const dx = toCenterX - fromCenterX;
        const dy = toCenterY - fromCenterY;
        
        // Spread arrows to prevent label overlap - DOUBLED spacing as requested
        const arrowSpacing = 16; // 16px spacing between arrows (was 8px - DOUBLED!)
        let offset = 0;
        if (totalInPair > 1) {
            offset = (relIndexInPair - (totalInPair - 1) / 2) * arrowSpacing;
        }
        
        // Add global offset based on all arrows from this table (not just to same target)
        // This prevents ALL arrows from exiting at exact center
        const globalSpacing = 10; // 10px spacing (was 5px - DOUBLED!)
        const globalOffset = (idx % 7 - 3) * globalSpacing; // Spread across 7 positions: -30, -20, -10, 0, 10, 20, 30
        
        if (Math.abs(dx) > Math.abs(dy)) {
            // Horizontal connection dominates
            if (dx > 0) {
                // From left to right: exit right side of from, enter left side of to
                fromX = fromPos.x + fromPos.w;
                fromY = fromCenterY + offset + globalOffset;
                toX = toPos.x;
                toY = toCenterY + offset + globalOffset;
            } else {
                // From right to left: exit left side of from, enter right side of to
                fromX = fromPos.x;
                fromY = fromCenterY + offset + globalOffset;
                toX = toPos.x + toPos.w;
                toY = toCenterY + offset + globalOffset;
            }
        } else {
            // Vertical connection dominates (most common)
            if (dy > 0) {
                // From top to bottom: exit bottom of from, enter top of to
                fromX = fromCenterX + offset + globalOffset;
                fromY = fromPos.y + 45;
                toX = toCenterX + offset + globalOffset;
                toY = toPos.y;
            } else {
                // From bottom to top: exit top of from, enter bottom of to
                fromX = fromCenterX + offset + globalOffset;
                fromY = fromPos.y;
                toX = toCenterX + offset + globalOffset;
                toY = toPos.y + 45;
            }
        }
        
        // SIMPLE PATH - default to straight L-shape, only route around if REALLY blocked
        let path;
        
        // Default: Simple L-shape (exit → cross → enter)
        if (Math.abs(dx) > Math.abs(dy)) {
            // Primarily horizontal movement
            path = `M${fromX},${fromY} L${fromX},${toY} L${toX},${toY}`;
        } else {
            // Primarily vertical movement  
            path = `M${fromX},${fromY} L${fromX},${toY} L${toX},${toY}`;
        }
        
        // ONLY route around if the two boxes themselves overlap in the crossing direction
        // (This means one box is directly blocking the other)
        const fromBox = { x1: fromPos.x, y1: fromPos.y, x2: fromPos.x + fromPos.w, y2: fromPos.y + 45 };
        const toBox = { x1: toPos.x, y1: toPos.y, x2: toPos.x + toPos.w, y2: toPos.y + 45 };
        
        if (Math.abs(dx) > Math.abs(dy)) {
            // Horizontal movement - check if boxes overlap vertically
            const overlapVertically = !(fromBox.y2 < toBox.y1 || fromBox.y1 > toBox.y2);
            if (overlapVertically) {
                // Boxes are on same horizontal plane - route around
                const clearance = 40;
                if (dy > 0 || fromBox.y1 < toBox.y1) {
                    // Route below
                    const clearY = Math.max(fromBox.y2, toBox.y2) + clearance;
                    path = `M${fromX},${fromY} L${fromX},${clearY} L${toX},${clearY} L${toX},${toY}`;
                } else {
                    // Route above
                    const clearY = Math.max(180, Math.min(fromBox.y1, toBox.y1) - clearance);
                    path = `M${fromX},${fromY} L${fromX},${clearY} L${toX},${clearY} L${toX},${toY}`;
                }
            }
        } else {
            // Vertical movement - check if boxes overlap horizontally
            const overlapHorizontally = !(fromBox.x2 < toBox.x1 || fromBox.x1 > toBox.x2);
            if (overlapHorizontally) {
                // Boxes are on same vertical plane - route around
                const clearance = 40;
                if (dx > 0 || fromBox.x1 < toBox.x1) {
                    // Route to the right
                    const clearX = Math.max(fromBox.x2, toBox.x2) + clearance;
                    path = `M${fromX},${fromY} L${clearX},${fromY} L${clearX},${toY} L${toX},${toY}`;
                } else {
                    // Route to the left
                    const clearX = Math.max(30, Math.min(fromBox.x1, toBox.x1) - clearance);
                    path = `M${fromX},${fromY} L${clearX},${fromY} L${clearX},${toY} L${toX},${toY}`;
                }
            }
        }
        
        // Add invisible wide stroke for easier hovering
        svg += `<path d="${path}" fill="none" stroke="transparent" stroke-width="12" 
            style="cursor:help;"
            data-from-table="${rel.from_table}" 
            data-from-col="${rel.from_col}" 
            data-from-type="${fromType}"
            data-to-table="${rel.to_table}" 
            data-to-col="${rel.to_col}"
            data-to-type="${toType}"
            data-relationship="${relationshipType}"
            onmousemove="showFKTooltip(event, this)"
            onmouseleave="hideFKTooltip()"/>`;
        
        // Add visible relationship arrow on top
        svg += `<path d="${path}" fill="none" stroke="#a371f7" stroke-width="1.5" 
            stroke-opacity="0.6" marker-end="url(#arrowhead)" class="fk-line"
            style="pointer-events:none;"/>`;
        
        // Add cardinality labels with better positioning based on arrow direction
        let labelFromX, labelFromY, labelToX, labelToY;
        
        if (Math.abs(dx) > Math.abs(dy)) {
            // Horizontal arrow - place labels to the side
            labelFromX = fromX + (dx > 0 ? 8 : -15);
            labelFromY = fromY - 5;
            labelToX = toX + (dx > 0 ? -15 : 8);
            labelToY = toY - 5;
        } else {
            // Vertical arrow - place labels offset horizontally
            labelFromX = fromX + 8;
            labelFromY = fromY + (dy > 0 ? 12 : -8);
            labelToX = toX + 8;
            labelToY = toY + (dy > 0 ? -8 : 12);
        }
        
        svg += `<text x="${labelFromX}" y="${labelFromY}" font-size="9" fill="#a371f7" font-weight="500" font-family="monospace">N</text>`;
        svg += `<text x="${labelToX}" y="${labelToY}" font-size="9" fill="#a371f7" font-weight="500" font-family="monospace">1</text>`;
    });
    
    // Draw table nodes
    Object.entries(positions).forEach(([name, pos]) => {
        const table = schema[name];
        if (!table) return;
        const cat = table.category || 'core';
        const isSelected = selectedTable === name;
        const colCount = table.columns?.length || 0;
        const hasFk = relations.some(r => r.from_table === name || r.to_table === name);
        
        // Calculate migration stats (only for old schema)
        let migrationBadge = '';
        if (currentView === 'old' && table.columns) {
            let toTenantCount = 0, toCentralCount = 0;
            
            table.columns.forEach(col => {
                if (!col.deprecated) {
                    if (col.targets && col.targets.length > 0) {
                        const hasTenant = col.targets.some(t => t.db === 'tenant' || !t.db || t.db === 'default');
                        const hasCentral = col.targets.some(t => t.db === 'central');
                        if (hasTenant) toTenantCount++;
                        if (hasCentral) toCentralCount++;
                    } else if (col.target) {
                        toTenantCount++;
                    }
                }
            });
            
            const total = table.columns.length;
            const tenantPct = total > 0 ? Math.round((toTenantCount / total) * 100) : 0;
            const centralPct = total > 0 ? Math.round((toCentralCount / total) * 100) : 0;
            
            // Build compact badge with both percentages
            if (tenantPct > 0 || centralPct > 0) {
                let badgeText = '';
                if (tenantPct > 0) badgeText += `T:${tenantPct}%`;
                if (centralPct > 0) {
                    if (badgeText) badgeText += ' ';
                    badgeText += `C:${centralPct}%`;
                }
                
                // Color based on presence
                let badgeColor;
                if (tenantPct > 0 && centralPct > 0) {
                    badgeColor = '#a371f7'; // Purple - both
                } else if (centralPct > 0) {
                    badgeColor = '#db6d28'; // Orange - central only
                } else {
                    badgeColor = '#3fb950'; // Green - tenant only
                }
                
                migrationBadge = `<text x="8" y="42" font-size="8" fill="${badgeColor}" font-weight="500">${badgeText}</text>`;
            } else {
                // Mostly deprecated
                migrationBadge = `<text x="8" y="42" font-size="8" fill="#f85149" font-weight="500">deprecated</text>`;
            }
        }
        
        svg += `<g class="node ${isSelected ? 'selected' : ''}" 
            data-table="${name}" 
            onclick="selectTable('${name}')"
            onmousedown="startDrag(event, '${name}')"
            style="cursor: move;"
            transform="translate(${pos.x},${pos.y})">
            <rect class="node-bg stroke-${cat}" width="${pos.w}" height="45"/>
            <rect class="node-stripe c-${cat}" x="0" y="0" width="3" height="45"/>
            <text class="node-text" x="8" y="16">${name.length > pos.w/6.5 ? name.slice(0,Math.floor(pos.w/6.5)-1)+'…' : name}</text>
            <text class="node-count" x="8" y="32">${colCount} cols${hasFk ? ' • FK' : ''}</text>
            ${migrationBadge}
        </g>`;
    });
    
    svg += '</svg>';
    const graphPanel = document.getElementById('graphPanel');
    graphPanel.innerHTML = svg;
    
    // Add global drag event listeners
    graphPanel.addEventListener('mousemove', drag);
    graphPanel.addEventListener('mouseup', endDrag);
    graphPanel.addEventListener('mouseleave', endDrag);
}

function startDrag(event, tableName) {
    if (event.button !== 0) return; // Only left mouse button
    event.stopPropagation(); // Prevent bubbling
    
    // Track initial mouse position
    mouseDownPos = { x: event.clientX, y: event.clientY };
    hasMoved = false;
    draggedTable = tableName;
    
    const svg = document.getElementById('graphPanel').querySelector('svg');
    const node = svg.querySelector(`[data-table="${tableName}"]`);
    const transform = node.getAttribute('transform');
    const match = transform.match(/translate\\(([-\\d.]+),([-\\d.]+)\\)/);
    
    if (match) {
        const nodeX = parseFloat(match[1]);
        const nodeY = parseFloat(match[2]);
        const svgRect = svg.getBoundingClientRect();
        dragOffset = {
            x: event.clientX - svgRect.left - nodeX,
            y: event.clientY - svgRect.top - nodeY
        };
    }
}

function drag(event) {
    if (!draggedTable || !mouseDownPos) return;
    
    // Check if mouse has moved more than 5px (threshold for drag vs click)
    const dx = Math.abs(event.clientX - mouseDownPos.x);
    const dy = Math.abs(event.clientY - mouseDownPos.y);
    
    if (dx > 5 || dy > 5) {
        hasMoved = true;
        isDragging = true;
        
        const svg = document.getElementById('graphPanel').querySelector('svg');
        const svgRect = svg.getBoundingClientRect();
        const node = svg.querySelector(`[data-table="${draggedTable}"]`);
        
        const newX = Math.max(0, event.clientX - svgRect.left - dragOffset.x);
        const newY = Math.max(0, event.clientY - svgRect.top - dragOffset.y);
        
        node.setAttribute('transform', `translate(${newX},${newY})`);
        node.style.opacity = '0.7';
        node.style.cursor = 'grabbing';
    }
}

function endDrag(event) {
    if (!draggedTable) return;
    
    const tableName = draggedTable;
    const svg = document.getElementById('graphPanel').querySelector('svg');
    const node = svg.querySelector(`[data-table="${tableName}"]`);
    
    if (hasMoved && isDragging) {
        // It was a DRAG - save the new position
        const transform = node.getAttribute('transform');
        const match = transform.match(/translate\\(([-\\d.]+),([-\\d.]+)\\)/);
        
        if (match) {
            const newX = parseFloat(match[1]);
            const newY = parseFloat(match[2]);
            
            // Save the new position
            const schema = getSchema();
            const positions = layoutTables(schema);
            positions[tableName] = { ...positions[tableName], x: newX, y: newY };
            
            // Update localStorage
            const savedPositions = loadSavedPositions();
            savedPositions[tableName] = { x: newX, y: newY };
            savePositions(savedPositions);
            
            // Re-render to update arrows
            renderGraph();
        }
    } else {
        // It was a CLICK - select the table to view columns
        selectTable(tableName);
    }
    
    node.style.opacity = '1';
    node.style.cursor = 'move';
    isDragging = false;
    draggedTable = null;
    mouseDownPos = null;
    hasMoved = false;
}

function selectTable(name) {
    selectedTable = name;
    renderGraph();
    showPanel(name);
}

function showPanel(name) {
    document.getElementById('detailPanel').classList.remove('collapsed');
    document.getElementById('detailTitle').textContent = name;
    
    const currentTable = getSchema()[name];
    if (currentTable) {
        document.getElementById('detailBadge').style.background = `var(--${categories[currentTable.category]?.color || 'dim'})`;
        document.getElementById('detailBadge').textContent = categories[currentTable.category]?.name || currentTable.category;
    }
    
    // Build comparison table - show 2 or 3 columns depending on view
    const schemaLabels = {
        'old': { col1: 'Old Schema (ctxweb)', col2: 'Migrates to Tenant DB →', col3: 'Migrates to Central DB →', showCol3: true },
        'new': { col1: 'New Tenant DB', col2: 'Source from Old Schema ←', col3: '', showCol3: false },
        'central': { col1: 'Central DB', col2: 'Source from Old Schema ←', col3: '', showCol3: false }
    };
    const labels = schemaLabels[currentView] || schemaLabels['old'];
    
    let html = '<div style="margin-bottom:10px;font-size:11px;color:var(--dim)">Click any column for detailed migration info. <span class="hide-on-small">Showing migration relationships. <strong style="color:var(--purple)">💡 Tip:</strong> Click PK/FK badges to highlight arrows!</span></div>';
    html += `<table class="comparison-table ${labels.showCol3 ? '' : 'two-column'}"><thead><tr>`;
    html += `<th class="schema-col old-schema">${labels.col1}</th>`;
    html += `<th class="schema-col new-schema">${labels.col2}</th>`;
    if (labels.showCol3) {
        html += `<th class="schema-col central-schema">${labels.col3}</th>`;
    }
    html += '</tr></thead><tbody>';
    
    // Check if table has columns
    if (!currentTable || !currentTable.columns) {
        const colspan = labels.showCol3 ? 3 : 2;
        html += `<tr><td colspan="${colspan}" class="missing">No columns found</td></tr>`;
    } else {
        // For each column in the current table
        currentTable.columns.forEach(col => {
            html += '<tr>';
            
            // Column 1: Always show current column (clickable for details)
            html += '<td class="schema-col old-schema">';
            const isDeprecated = col.deprecated;
            const hasMigration = col.target || (col.targets && col.targets.length > 0);
            
            html += `<div class="${isDeprecated ? 'deprecated' : ''}" style="cursor:pointer" onclick="selectColumn('${name}','${col.name}')">`;
            html += `<span class="col-name">${col.name}</span>`;
            html += `<span class="col-type">${col.type}</span>`;
            html += '<div class="col-badges">';
            if (col.pk) html += `<span class="badge pk" onclick="event.stopPropagation(); highlightPKRelations('${name}','${col.name}')" title="Click to highlight FK arrows referencing this">PK</span>`;
            if (col.fk) html += `<span class="badge fk" onclick="event.stopPropagation(); highlightFKRelation('${name}','${col.name}')" title="Click to highlight FK arrow">FK</span>`;
            if (col.uk) html += '<span class="badge uk">UK</span>';
            if (currentView === 'old') {
                if (isDeprecated) html += '<span style="color:var(--red);margin-left:5px">❌</span>';
                else if (hasMigration) html += '<span style="color:var(--green);margin-left:5px">→</span>';
            } else if (col.source) {
                html += '<span style="color:var(--blue);margin-left:5px">←</span>';
            }
            html += '</div></div>';
            html += '</td>';
            
            // Column 2: Context-dependent
            html += '<td class="schema-col new-schema">';
            if (currentView === 'old') {
                // OLD SCHEMA VIEW: Show tenant migration targets
                let tenantTargets = [];
                if (col.targets && col.targets.length > 0) {
                    tenantTargets = col.targets.filter(t => t.db === 'tenant' || !t.db || t.db === 'default');
                } else if (col.target && !col.deprecated) {
                    const [targetTable, targetCol] = col.target.split('.');
                    tenantTargets = [{ table: targetTable, column: targetCol }];
                }
                
                if (tenantTargets.length > 0) {
                    html += '<div style="display:flex;flex-direction:column;gap:3px;">';
                    tenantTargets.forEach(target => {
                        html += `<div style="cursor:pointer;padding:2px 6px;background:var(--bg);border-left:2px solid var(--green);border-radius:3px;word-wrap:break-word;overflow-wrap:break-word;" onclick="navigateTo('new','${target.table}','${target.column}')">`;
                        html += `<span class="col-name" style="word-break:break-word;">${target.table}.${target.column}</span>`;
                        html += '</div>';
                    });
                    html += '</div>';
                } else if (isDeprecated) {
                    html += '<span style="color:var(--red);font-size:9px;">Not migrated</span>';
                } else {
                    html += '<span class="missing">—</span>';
                }
            } else {
                // NEW/CENTRAL VIEW: Show source from old schema (clickable!)
                if (col.source) {
                    let srcTable, srcCol;
                    const src = col.source.trim();
                    
                    if (src.startsWith('tenant.')) {
                        const parts = src.replace('tenant.', '').split('.');
                        srcTable = parts[0];
                        srcCol = parts.length > 1 ? parts[1] : null;
                    } else if (src.includes('.')) {
                        const parts = src.split('.');
                        srcTable = parts[0];
                        srcCol = parts.length > 1 ? parts[1] : null;
                    } else {
                        srcTable = 'sysadmin_systemsettings';
                        srcCol = src;
                    }
                    
                    html += `<div style="cursor:pointer;padding:2px 6px;background:var(--bg);border-left:2px solid var(--blue);border-radius:3px;word-wrap:break-word;overflow-wrap:break-word;" onclick="navigateTo('old','${srcTable}','${srcCol}')">`;
                    html += `<span class="col-name" style="word-break:break-word;">${srcTable}.${srcCol}</span>`;
                    html += '</div>';
                } else {
                    html += '<span class="missing">—</span>';
                }
            }
            html += '</td>';
            
            // Column 3: Only show for old schema view
            if (labels.showCol3) {
                html += '<td class="schema-col central-schema">';
                if (currentView === 'old') {
                    // OLD SCHEMA VIEW: Show central migration targets
                    let centralTargets = [];
                    if (col.targets && col.targets.length > 0) {
                        centralTargets = col.targets.filter(t => t.db === 'central');
                    }
                    
                    if (centralTargets.length > 0) {
                        html += '<div style="display:flex;flex-direction:column;gap:3px;">';
                        centralTargets.forEach(target => {
                            html += `<div style="cursor:pointer;padding:2px 6px;background:var(--bg);border-left:2px solid var(--orange);border-radius:3px;word-wrap:break-word;overflow-wrap:break-word;" onclick="navigateTo('central','${target.table}','${target.column}')">`;
                            html += `<span class="col-name" style="word-break:break-word;">${target.table}.${target.column}</span>`;
                            html += '</div>';
                        });
                        html += '</div>';
                    } else {
                        html += '<span class="missing">—</span>';
                    }
                }
                html += '</td>';
            }
            
            html += '</tr>';
        });
    }
    
    html += '</tbody></table>';
    document.getElementById('colsList').innerHTML = html;
    document.getElementById('migrationPanel').innerHTML = '<div class="empty-state"><h4>Select a column</h4><p>Click any column above for migration details</p></div>';
}

function selectColumn(tableName, colName) {
    // Find and highlight the column item
    document.querySelectorAll('.col-item').forEach(el => el.classList.remove('selected'));
    const colItems = document.querySelectorAll('.col-item');
    colItems.forEach(item => {
        if (item.querySelector('.col-name')?.textContent === colName) {
            item.classList.add('selected');
        }
    });
    
    const table = getSchema()[tableName];
    if (!table) return;
    const col = table.columns.find(c => c.name === colName);
    if (!col) return;
    
    let html = '<div class="migration-title">Column Details</div>';
    
    // Current column info
    const schemaLabel = currentView === 'old' ? 'ctxweb (Old)' : (currentView === 'central' ? 'Central DB' : 'Tenant DB');
    html += `<div class="lineage-box" style="border-left-color:var(--blue)">
        <div class="lineage-label">Current: ${schemaLabel}</div>
        <div class="lineage-value">${tableName}.${colName}</div>
        <div style="font-size:9px;color:var(--dim);margin-top:3px">${col.type}${col.pk ? ' • PRIMARY KEY' : ''}${col.fk ? ' • FOREIGN KEY' : ''}${col.uk ? ' • UNIQUE' : ''}</div>
    </div>`;
    
    // Show FK reference (for any schema)
    if (col.fk && col.fk_ref) {
        const [refTable, refCol] = col.fk_ref;
        html += '<div class="lineage-arrow" style="color:var(--purple)">⤵ FK references</div>';
        html += `<div class="lineage-box clickable" style="border-left-color:var(--purple)" onclick="navigateTo('${currentView}','${refTable}','${refCol}')">
            <div class="lineage-label">References <span style="font-size:8px;color:var(--blue)">→ click to view</span></div>
            <div class="lineage-value">${refTable}.${refCol}</div>
        </div>`;
    }
    
    // Migration details based on current view
    if (currentView === 'old') {
        // Old schema: show where it migrates TO (supports multi-target)
        if ((col.target || (col.targets && col.targets.length > 0)) && !col.deprecated) {
            // Handle multi-target format
            if (col.targets && col.targets.length > 0) {
                html += '<div class="lineage-arrow" style="color:var(--green)">↓ migrates to</div>';
                
                col.targets.forEach((target, idx) => {
                    const targetTable = target.table || '';
                    const targetCol = target.column || '';
                    const targetDb = target.db || 'tenant';
                    const targetSchema = targetDb === 'central' ? 'central' : 'new';
                    const targetLabel = targetDb === 'central' ? 'Central DB' : 'Tenant DB';
                    const targetColor = targetDb === 'central' ? 'var(--orange)' : 'var(--green)';
                    
                    html += `<div class="lineage-box target clickable" style="border-left-color:${targetColor}" onclick="navigateTo('${targetSchema}','${targetTable}','${targetCol}')">
                        <div class="lineage-label">${idx + 1}. Target (${targetLabel}) <span style="font-size:8px;color:var(--blue)">→ click to view</span></div>
                        <div class="lineage-value">${targetTable}.${targetCol}</div>
                    </div>`;
                    
                    if (target.sql) {
                        html += `<div class="sql-label">Migration SQL #${idx + 1}</div>
                            <div class="sql-box">${target.sql}</div>`;
                    }
                });
            } else {
                // Handle old single-target format (backward compatible)
                const [targetTable, targetCol] = col.target.includes('.') ? col.target.split('.') : [col.target, null];
                html += '<div class="lineage-arrow" style="color:var(--green)">↓ migrates to</div>';
                html += `<div class="lineage-box target clickable" onclick="navigateTo('new','${targetTable}','${targetCol || ''}')">
                    <div class="lineage-label">Target (Tenant DB) <span style="font-size:8px;color:var(--blue)">→ click to view</span></div>
                    <div class="lineage-value">${col.target}</div>
                </div>`;
                
                if (col.sql) {
                    html += `<div class="sql-label">Migration SQL</div>
                        <div class="sql-box">${col.sql}</div>`;
                }
            }
        } else if (col.deprecated) {
            html += '<div class="lineage-arrow" style="color:var(--red)">✕ deprecated</div>';
            html += `<div class="lineage-box deprecated">
                <div class="lineage-label">Not Migrated</div>
                <div class="reason">${col.reason || 'Field will be deprecated in new schema'}</div>
            </div>`;
        }
    } else {
        // New/Central schema: show where it comes FROM
        if (col.source) {
            let srcTable, srcCol, srcView = 'old';
            const src = col.source.trim();
            
            if (src.startsWith('tenant.')) {
                // Central schema referencing tenant schema: "tenant.users.field"
                const parts = src.replace('tenant.', '').split('.');
                srcTable = parts[0];
                srcCol = parts.length > 1 ? parts[1] : null;
                srcView = 'new';
            } else if (src.includes('.')) {
                // Explicit table.column format
                const parts = src.split('.');
                srcTable = parts[0];
                srcCol = parts.length > 1 ? parts[1] : null;
            } else {
                // Just column name - assume sysadmin_systemsettings as default source table
                srcTable = 'sysadmin_systemsettings';
                srcCol = src;
            }
            
            const srcLabel = srcView === 'new' ? 'Tenant DB' : 'ctxweb (Old)';
            html += '<div class="lineage-arrow" style="color:var(--orange)">↑ source from</div>';
            html += `<div class="lineage-box source clickable" onclick="navigateTo('${srcView}','${srcTable}','${srcCol || ''}')">
                <div class="lineage-label">Source (${srcLabel}) <span style="font-size:8px;color:var(--blue)">→ click to view</span></div>
                <div class="lineage-value">${srcTable}.${srcCol || src}</div>
            </div>`;
        } else {
            html += `<div style="font-size:10px;color:var(--dim);margin-top:8px;font-style:italic">New field - no source mapping</div>`;
        }
    }
    
    document.getElementById('migrationPanel').innerHTML = html;
}

function navigateTo(view, tableName, colName) {
    // Check if table exists in target view
    const targetSchema = schemaData[view] || {};
    if (!targetSchema[tableName]) {
        console.warn(`Table "${tableName}" not found in ${view} schema`);
        alert(`Table "${tableName}" not found in ${view} schema`);
        return;
    }
    
    // Switch tab
    currentView = view;
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.dataset.view === view);
    });
    
    // Update everything
    selectedTable = tableName;
    renderLegend();
    renderGraph();
    showPanel(tableName);
    
    // Scroll the graph to show the selected table
    setTimeout(() => {
        const selectedNode = document.querySelector('.node.selected');
        if (selectedNode) {
            selectedNode.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        }
    }, 50);
    
    // Highlight and show specific column if provided
    if (colName) {
        setTimeout(() => {
            selectColumn(tableName, colName);
            // Scroll the column into view
            const colItems = document.querySelectorAll('.col-item');
            colItems.forEach(item => {
                const nameEl = item.querySelector('.col-name');
                if (nameEl && nameEl.textContent === colName) {
                    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        }, 100);
    }
}

function closePanel() {
    document.getElementById('detailPanel').classList.add('collapsed');
    selectedTable = null;
    renderGraph();
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        currentView = tab.dataset.view;
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        selectedTable = null;
        document.getElementById('detailPanel').classList.add('collapsed');
        renderLegend();
        renderGraph();
    });
});

// FK Tooltip functions
let fkTooltip = null;
let currentHoverPath = null;
let currentHoverTables = [];

function showFKTooltip(event, element) {
    const fromTable = element.dataset.fromTable;
    const fromCol = element.dataset.fromCol;
    const fromType = element.dataset.fromType;
    const toTable = element.dataset.toTable;
    const toCol = element.dataset.toCol;
    const toType = element.dataset.toType;
    const relationship = element.dataset.relationship;
    
    // Highlight the visible FK line (next sibling of invisible hover path)
    const visiblePath = element.nextElementSibling;
    if (visiblePath && visiblePath.classList.contains('fk-line')) {
        currentHoverPath = visiblePath;
        visiblePath.classList.add('hovered');
    }
    
    // Highlight the connected table nodes
    const fromNode = document.querySelector(`.node[onclick*="'${fromTable}'"]`);
    const toNode = document.querySelector(`.node[onclick*="'${toTable}'"]`);
    if (fromNode) {
        fromNode.classList.add('fk-connected');
        currentHoverTables.push(fromNode);
    }
    if (toNode) {
        toNode.classList.add('fk-connected');
        currentHoverTables.push(toNode);
    }
    
    if (!fkTooltip) {
        fkTooltip = document.createElement('div');
        fkTooltip.className = 'fk-tooltip';
        document.body.appendChild(fkTooltip);
    }
    
    fkTooltip.innerHTML = `
        <div class="tooltip-title">🔗 Foreign Key Relationship</div>
        <div class="tooltip-row"><span class="tooltip-label">From:</span> <strong>${fromTable}.${fromCol}</strong> (${fromType})</div>
        <div class="tooltip-row"><span class="tooltip-label">To:</span> <strong>${toTable}.${toCol}</strong> (${toType})</div>
        <div class="tooltip-row"><span class="tooltip-label">Cardinality:</span> <strong>${relationship}</strong> (Many-to-One)</div>
        <div class="tooltip-row" style="margin-top:4px;color:var(--dim);font-size:9px;">
            ↑ Many rows in <strong>${fromTable}</strong> can reference one row in <strong>${toTable}</strong>
        </div>
    `;
    
    fkTooltip.style.display = 'block';
    fkTooltip.style.left = (event.pageX + 15) + 'px';
    fkTooltip.style.top = (event.pageY + 15) + 'px';
}

function hideFKTooltip() {
    if (fkTooltip) {
        fkTooltip.style.display = 'none';
    }
    // Reset the highlighted FK line
    if (currentHoverPath) {
        currentHoverPath.classList.remove('hovered');
        currentHoverPath = null;
    }
    // Reset highlighted table nodes
    currentHoverTables.forEach(node => {
        node.classList.remove('fk-connected');
    });
    currentHoverTables = [];
}

// Persistent highlight state (cleared on click elsewhere)
let persistentHighlights = { arrows: [], tables: [] };

function clearPersistentHighlights() {
    persistentHighlights.arrows.forEach(arrow => arrow.classList.remove('hovered'));
    persistentHighlights.tables.forEach(table => table.classList.remove('fk-connected'));
    persistentHighlights = { arrows: [], tables: [] };
}

function highlightFKRelation(tableName, columnName) {
    clearPersistentHighlights();
    
    // Find the FK relationship for this column
    const schema = window.currentSchemaData[currentView];
    const table = schema[tableName];
    const column = table?.columns?.find(c => c.name === columnName);
    
    if (!column || !column.fk || !column.fk_ref) {
        console.log('No FK found for', tableName, columnName);
        return;
    }
    
    const [refTable, refCol] = column.fk_ref;
    console.log('FK:', tableName + '.' + columnName, '→', refTable + '.' + refCol);
    
    // Find all FK arrows from this table.column to referenced table
    // Check BOTH invisible path and visible path for dataset
    const allInvisiblePaths = document.querySelectorAll('path[data-from-table]');
    allInvisiblePaths.forEach(invisiblePath => {
        if (invisiblePath.dataset.fromTable === tableName && 
            invisiblePath.dataset.fromCol === columnName) {
            // Found matching arrow - highlight the visible path (next sibling)
            const visiblePath = invisiblePath.nextElementSibling;
            if (visiblePath && visiblePath.classList.contains('fk-line')) {
                visiblePath.classList.add('hovered');
                persistentHighlights.arrows.push(visiblePath);
                console.log('Highlighted arrow from', tableName, 'to', invisiblePath.dataset.toTable);
            }
        }
    });
    
    // Highlight the connected tables
    const fromNode = document.querySelector(`[data-table="${tableName}"]`);
    const toNode = document.querySelector(`[data-table="${refTable}"]`);
    
    if (fromNode) {
        fromNode.classList.add('fk-connected');
        persistentHighlights.tables.push(fromNode);
    }
    if (toNode) {
        toNode.classList.add('fk-connected');
        persistentHighlights.tables.push(toNode);
    }
    
    // Scroll to the graph if needed
    document.getElementById('graphPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function highlightPKRelations(tableName, columnName) {
    clearPersistentHighlights();
    
    console.log('PK Relations for', tableName + '.' + columnName);
    
    // Find all FK arrows that reference this PK
    // Use the invisible path dataset to find matches
    const allInvisiblePaths = document.querySelectorAll('path[data-to-table]');
    allInvisiblePaths.forEach(invisiblePath => {
        if (invisiblePath.dataset.toTable === tableName && 
            invisiblePath.dataset.toCol === columnName) {
            // Found an arrow pointing to this PK - highlight the visible path (next sibling)
            const visiblePath = invisiblePath.nextElementSibling;
            if (visiblePath && visiblePath.classList.contains('fk-line')) {
                visiblePath.classList.add('hovered');
                persistentHighlights.arrows.push(visiblePath);
                console.log('Highlighted arrow from', invisiblePath.dataset.fromTable, 'to', tableName);
                
                // Also highlight the source table
                const fromTable = invisiblePath.dataset.fromTable;
                const fromNode = document.querySelector(`[data-table="${fromTable}"]`);
                if (fromNode && !persistentHighlights.tables.includes(fromNode)) {
                    fromNode.classList.add('fk-connected');
                    persistentHighlights.tables.push(fromNode);
                }
            }
        }
    });
    
    // Highlight the PK table itself
    const pkNode = document.querySelector(`[data-table="${tableName}"]`);
    if (pkNode && !persistentHighlights.tables.includes(pkNode)) {
        pkNode.classList.add('fk-connected');
        persistentHighlights.tables.push(pkNode);
    }
    
    // Scroll to the graph if needed
    document.getElementById('graphPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Clear highlights when clicking elsewhere
document.addEventListener('click', function(event) {
    // Don't clear if clicking on a badge
    if (event.target.classList.contains('badge')) return;
    // Don't clear if clicking on an FK arrow
    if (event.target.tagName === 'path') return;
    
    clearPersistentHighlights();
});

renderLegend();
renderGraph();
</script>
</body>
</html>'''
    
    return html


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    
    # Read schema files
    old_path = os.path.join(repo_root, 'schemas', 'old', 'schema.sql')
    new_path = os.path.join(repo_root, 'schemas', 'new', 'tenant_schema.sql')
    central_path = os.path.join(repo_root, 'schemas', 'new', 'central_schema.sql')
    mappings_path = os.path.join(repo_root, 'scripts', 'field_mappings.json')
    
    print("Parsing SQL schema files...")
    
    with open(old_path, 'r') as f:
        old_sql = f.read()
    with open(new_path, 'r') as f:
        new_sql = f.read()
    with open(central_path, 'r') as f:
        central_sql = f.read()
    with open(mappings_path, 'r') as f:
        mappings_data = json.load(f)
    
    old_tables, old_fk = parse_sql_schema(old_sql, 'old')
    new_tables, new_fk = parse_sql_schema(new_sql, 'new')
    central_tables, central_fk = parse_sql_schema(central_sql, 'central')
    
    print(f"  Old schema: {len(old_tables)} tables, {sum(len(t['columns']) for t in old_tables.values())} columns, {len(old_fk)} FK relations")
    print(f"  New tenant: {len(new_tables)} tables, {sum(len(t['columns']) for t in new_tables.values())} columns, {len(new_fk)} FK relations")
    print(f"  Central: {len(central_tables)} tables, {sum(len(t['columns']) for t in central_tables.values())} columns, {len(central_fk)} FK relations")
    
    # Get deprecated tables
    deprecated_tables = mappings_data.get('_deprecated_tables', {})
    
    # Filter out meta keys from mappings
    field_mappings = {k: v for k, v in mappings_data.items() if not k.startswith('_')}
    
    # Merge mappings into old schema
    old_tables = merge_mappings(old_tables, field_mappings, deprecated_tables)
    
    # Count mappings
    mapped = sum(1 for t in old_tables.values() for c in t['columns'] if c.get('target'))
    deprecated = sum(1 for t in old_tables.values() for c in t['columns'] if c.get('deprecated'))
    print(f"  Mapped fields: {mapped}")
    print(f"  Deprecated fields: {deprecated}")
    
    # Generate HTML
    html = generate_html(old_tables, new_tables, central_tables, old_fk, new_fk, central_fk)
    
    output_path = os.path.join(repo_root, 'tools', 'schema_diagram.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"\n✅ Generated: {output_path}")


if __name__ == '__main__':
    main()
