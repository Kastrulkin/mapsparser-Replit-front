#!/bin/bash
# scripts/rollback_phase_3_5.sh
# Rollback script for Phase 3.5 (Data Integrity & Constraints)

# Exit on error
set -e

DB_NAME="reports.db"
DB_TYPE=${DB_TYPE:-sqlite} # Default to sqlite, can be set to postgres

echo "🛑 STRICT ROLLBACK INITIATED..."

if [ "$DB_TYPE" == "sqlite" ]; then
    echo "📂 Detected SQLite environment ($DB_NAME)"
    
    # SQLite doesn't support DROP CONSTRAINT easily (requires table recreation).
    # Since we are modifying 'UserServices' and 'ExternalBusinessReviews', we might just need to restore from backup tables.
    
    sqlite3 $DB_NAME <<EOF
    BEGIN TRANSACTION;

    -- 1. Rollback UserServices from Backup
    DROP TABLE IF EXISTS UserServices;
    CREATE TABLE UserServices AS SELECT * FROM UserServices_backup;
    -- Recreate original indices if any (checking schema_postgres.sql for reference)
    CREATE INDEX IF NOT EXISTS idx_user_services_user ON UserServices(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_services_business ON UserServices(business_id);
    
    -- 2. Rollback ExternalBusinessReviews from Backup
    DROP TABLE IF EXISTS ExternalBusinessReviews;
    CREATE TABLE ExternalBusinessReviews AS SELECT * FROM ExternalBusinessReviews_backup;
    
    COMMIT;
EOF
    echo "✅ SQLite Rollback completed (Restored from _backup tables)."

else
    echo "🐘 Detected Postgres environment"
    # Postgres Rollback commands
    
    # Assumes psql credentials are set in environment
    psql -c "ALTER TABLE UserServices DROP CONSTRAINT IF EXISTS fk_user;"
    psql -c "DROP INDEX IF EXISTS idx_reviews_unique;"
    
    # Optional: Restore data from backup if data corruption occurred
    # psql -c "TRUNCATE UserServices; INSERT INTO UserServices SELECT * FROM UserServices_backup;"
    
    echo "✅ Postgres Constraints dropped."
fi

echo "⚠️  NOTE: If you need to restore full DB state, use the file-level backup created before migration."
