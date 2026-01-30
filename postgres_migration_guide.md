# PostgreSQL Migration Guide (Production)

This guide details the steps to migrate the BeautyBot server (HP C2-M4-D20) from SQLite to PostgreSQL.
**Constraints**: 2 vCPU, 4GB RAM, 20GB Disk.

## 1. Install PostgreSQL
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgresql-client -y
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

## 2. Configure Resources (CRITICAL)
Due to limited RAM (4GB) and Disk (20GB), you **MUST** apply these settings to prevent OOM kills and disk exhaustion.

**Edit Config:**
```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
# (Check version: might be 16 or 15 depending on Ubuntu 24.04)
```

**Apply these values (Find and replace or append):**
```ini
# --- BeautyBot Optimized Config ---
shared_buffers = 1GB           # 25% of RAM
effective_cache_size = 3GB     # Filesystem cache hint
work_mem = 16MB                # Low to prevent mem spikes per connection
maintenance_work_mem = 256MB   # For vacuums
max_connections = 50           # Strict limit (each conn uses RAM)

# --- DISK (Avoid Full Disk) ---
max_wal_size = 1GB             # Rotate logs aggressively
wal_keep_size = 256MB
log_min_duration_statement = 5000 # Log only slow queries > 5s
logging_collector = on
log_directory = 'log'
log_rotation_age = 1d
log_rotation_size = 100MB
```

**Restart Postgres:**
```bash
sudo systemctl restart postgresql
```

## 3. Create Database & User
```bash
sudo -u postgres psql
```

Inside SQL shell:
```sql
CREATE DATABASE beautybot;
CREATE USER beautybot_user WITH ENCRYPTED PASSWORD 'YOUR_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE beautybot TO beautybot_user;
-- Grant schema usage
\c beautybot
GRANT ALL ON SCHEMA public TO beautybot_user;
\q
```

## 4. Run Migration
1. **Stop the Worker** (Prevent new data writing):
   ```bash
   sudo systemctl stop beautybot-worker
   ```

2. **Backup SQLite** (Just in case):
   ```bash
   cp src/reports.db src/reports.db.bak
   ```

3. **Run Migration Script**:
   Set the env var locally for the script (replace password):
   ```bash
   export DATABASE_URL="postgresql://beautybot_user:YOUR_STRONG_PASSWORD@localhost:5432/beautybot"
   pip install psycopg2-binary || sudo apt install python3-psycopg2
   
   python3 scripts/migrate_to_postgres.py
   ```
   *Expect output: "🎉 Migration Completed Successfully!"*

## 5. Switch Application
Update `.env` file:
```bash
nano .env
```
Add/Change:
```ini
DB_TYPE=postgres
DATABASE_URL=postgresql://beautybot_user:YOUR_STRONG_PASSWORD@localhost:5432/beautybot
```

## 6. Restart Services
```bash
sudo systemctl restart beautybot-backend
sudo systemctl start beautybot-worker
```

## 7. Verification
Check resources and logs:
```bash
# Check Disk
df -h
# Expect: > 5GB free

# Check RAM
free -h
# Expect: available > 500MB

# Check Logs
tail -f worker.log
```
