import sqlite3
import psycopg2
import psycopg2.extras
import os
import re
import sys
from pathlib import Path

# Config
SQLITE_DB_PATH = 'src/reports.db'
SCHEMA_FILE = 'src/schema_postgres.sql'
DATABASE_URL = os.getenv('DATABASE_URL')  # Required

def get_boolean_columns(schema_path):
    """
    Parses the SQL schema file to find columns defined as BOOLEAN.
    Returns a dict: {'TableName': {'col1', 'col2'}}
    """
    with open(schema_path, 'r') as f:
        sql = f.read()
    
    # Remove comments
    sql = re.sub(r'--.*', '', sql)
    
    # Split by CREATE TABLE
    tables = {}
    
    # improved regex to capture table name and body
    # Matches "CREATE TABLE Name (" then content until ");"
    table_matches = re.finditer(r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);', sql, re.DOTALL | re.IGNORECASE)
    
    for match in table_matches:
        table_name = match.group(1)
        body = match.group(2)
        
        bool_cols = set()
        # line by line
        for line in body.split(','):
            line = line.strip()
            if not line: continue
            
            # Check for column definition, ignore constraints
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_def = ' '.join(parts[1:]).upper()
                if 'BOOLEAN' in col_def:
                    bool_cols.add(col_name)
                    
        tables[table_name] = bool_cols
        
    return tables

def migrate():
    if not DATABASE_URL:
        print("❌ DATABASE_URL env var is missing!")
        sys.exit(1)
        
    print(f"🔄 Starting migration from {SQLITE_DB_PATH} to PostgreSQL...")
    
    # 1. Connect to SQLite
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ SQLite DB not found at {SQLITE_DB_PATH}")
        sys.exit(1)
        
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # 2. Connect to Postgres
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to Postgres: {e}")
        sys.exit(1)

    # 3. Analyze Schema for Bools
    bool_map = get_boolean_columns(SCHEMA_FILE)
    print(f"📋 Detected Boolean columns for conversion: {bool_map}")

    # 4. Apply Schema
    print("🔨 Applying PostgreSQL Data Schema...")
    with open(SCHEMA_FILE, 'r') as f:
        schema_sql = f.read()
        try:
            pg_cursor.execute(schema_sql)
            pg_conn.commit()
            print("✅ Schema applied.")
        except Exception as e:
            print(f"❌ Schema application failed: {e}")
            pg_conn.rollback()
            sys.exit(1)
            
    # 5. Migrate Data
    tables = bool_map.keys()
    
    # Order matters due to foreign keys! 
    # We should disable FK checks or order carefully.
    # Postgres doesn't easily disable FK checks globally for a session without superuser.
    # Best to truncate all validation? 
    # Easier: Use correct order.
    # Order: Users -> Networks -> Businesses -> The rest...
    ordered_tables = [
        'Users', 'Networks', 'Businesses', 
        'UserSessions', 'ParseQueue', 'SyncQueue', 'ProxyServers', 'AIPrompts', 
        'Masters', 'BusinessOptimizationWizard', 'PricelistOptimizations',
        'MapParseResults', 'BusinessMapLinks', 'FinancialTransactions', 
        'FinancialMetrics', 'ROIData', 'UserServices', 'UserNews', 
        'TelegramBindTokens', 'ReviewExchangeParticipants', 'ReviewExchangeDistribution',
        'ExternalBusinessReviews', 'ExternalBusinessPosts', 'ExternalBusinessPhotos', 
        'ExternalBusinessStats', 'WordstatKeywords', 'BusinessMetricsHistory', 'AIAgents'
    ]
    
    # Verify we didn't miss any from the parsed list
    for t in tables:
        if t not in ordered_tables:
            ordered_tables.append(t)
            
    for table in ordered_tables:
        print(f"📦 Migrating table: {table}")
        
        # Check if table exists in SQLite
        try:
            sqlite_cursor.execute(f"SELECT * FROM {table}")
        except sqlite3.OperationalError:
            print(f"   ⚠️ Table {table} not found in SQLite. Skipping.")
            continue
            
        rows = sqlite_cursor.fetchall()
        if not rows:
            print("   ℹ️ Empty table.")
            continue
            
        # Get columns
        columns = [description[0] for description in sqlite_cursor.description]
        
        # Prepare data with casting
        bool_cols = bool_map.get(table, set())
        
        clean_rows = []
        for row in rows:
            row_dict = dict(row)
            values = []
            for col in columns:
                val = row_dict[col]
                # Cast boolean
                if col in bool_cols:
                    values.append(bool(val) if val is not None else None)
                else:
                    values.append(val)
            clean_rows.append(tuple(values))
            
        # Bulk Insert
        # Bulk Insert
        # Postgres lowercases unquoted identifiers in CREATE TABLE. We match that here.
        pg_table = table.lower()
        pg_cols = [c.lower() for c in columns]
        cols_str = ', '.join([f'"{c}"' for c in pg_cols]) 
        
        query = f'INSERT INTO "{pg_table}" ({cols_str}) VALUES %s ON CONFLICT (id) DO NOTHING'
        try:
            psycopg2.extras.execute_values(pg_cursor, query, clean_rows)
            print(f"   ✅ Migrated {len(clean_rows)} rows.")
        except Exception as e:
            print(f"   ❌ Failed to insert into {table}: {e}")
            pg_conn.rollback()
            # Try to continue? No, inconsistent state.
            sys.exit(1)
            
    pg_conn.commit()
    print("🎉 Migration Completed Successfully!")
    sqlite_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    migrate()
