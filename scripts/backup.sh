#!/bin/bash
# ===========================================
# Galatea Cloud - SQLite Database Backup
# ===========================================
# Creates timestamped backups of the SQLite database
# Keeps last 7 days of backups
#
# Run manually:
#   ./backup.sh
#
# Or via cron (daily at 3 AM):
#   0 3 * * * /opt/galatea/scripts/backup.sh >> /opt/galatea/backups/backup.log 2>&1
# ===========================================

set -e

# Configuration
GALATEA_DIR="${GALATEA_DIR:-/opt/galatea}"
DB_PATH="${GALATEA_DIR}/data/galatea.db"
BACKUP_DIR="${GALATEA_DIR}/backups"
RETENTION_DAYS=7

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_HUMAN=$(date "+%Y-%m-%d %H:%M:%S")

# Backup filename
BACKUP_FILE="${BACKUP_DIR}/galatea_${TIMESTAMP}.db"

echo "[$DATE_HUMAN] Starting backup..."

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "[$DATE_HUMAN] ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Create backup using SQLite's backup command
# This ensures a consistent backup even if the database is in use
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    # Get file sizes
    ORIGINAL_SIZE=$(du -h "$DB_PATH" | cut -f1)
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    
    echo "[$DATE_HUMAN] Backup created: $BACKUP_FILE"
    echo "[$DATE_HUMAN] Original: $ORIGINAL_SIZE, Backup: $BACKUP_SIZE"
    
    # Compress the backup
    gzip "$BACKUP_FILE"
    COMPRESSED_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
    echo "[$DATE_HUMAN] Compressed: ${BACKUP_FILE}.gz ($COMPRESSED_SIZE)"
else
    echo "[$DATE_HUMAN] ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups
echo "[$DATE_HUMAN] Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "galatea_*.db.gz" -type f -mtime +$RETENTION_DAYS -delete

# Count remaining backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/galatea_*.db.gz 2>/dev/null | wc -l)
echo "[$DATE_HUMAN] Backup complete. Total backups: $BACKUP_COUNT"

# Optional: Verify backup integrity
echo "[$DATE_HUMAN] Verifying backup integrity..."
# Use mktemp for secure temporary file creation (prevents symlink attacks)
VERIFY_FILE=$(mktemp /tmp/galatea_verify.XXXXXX.db)
gunzip -c "${BACKUP_FILE}.gz" > "$VERIFY_FILE"
INTEGRITY=$(sqlite3 "$VERIFY_FILE" "PRAGMA integrity_check;" 2>&1)
rm -f "$VERIFY_FILE"

if [ "$INTEGRITY" = "ok" ]; then
    echo "[$DATE_HUMAN] Integrity check: PASSED"
else
    echo "[$DATE_HUMAN] WARNING: Integrity check failed: $INTEGRITY"
fi

echo "[$DATE_HUMAN] Done."
