#!/usr/bin/env bash
# Captures a point-in-time backup of the Hikari production data plane.
# Output: /opt/hikari/backups/hikari-YYYY-MM-DD-HHMMSS.zip
#
# Contents of the archive:
#   - mariadb dump (logical, includes all tables and grants)
#   - elasticsearch indices (filesystem snapshot of the data volume)
#   - CTFd uploads directory
#   - .env.production (so the backup is self-contained for a restore)
#
# Idempotent and safe to schedule via cron. Exits non-zero on any failure so
# cron's MAILTO captures the error.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.production.yml"
ENV_FILE="$SCRIPT_DIR/.env.production"
BACKUP_DIR=${BACKUP_DIR:-/opt/hikari/backups}
RETENTION_DAYS=${RETENTION_DAYS:-14}

[[ -f "$COMPOSE_FILE" ]] || { echo "compose file not found: $COMPOSE_FILE" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "env file not found: $ENV_FILE" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
stamp=$(date +%Y-%m-%d-%H%M%S)
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

archive="$BACKUP_DIR/hikari-$stamp.zip"
echo "creating backup: $archive"

# 1. MariaDB logical dump (consistent snapshot via --single-transaction).
echo "  - dumping mariadb"
docker compose -f "$COMPOSE_FILE" exec -T db \
  mariadb-dump -uctfd -pctfd --single-transaction --routines --triggers ctfd \
  > "$workdir/ctfd.sql"

# 2. CTFd uploads (small, copy as-is from the named volume).
echo "  - copying ctfd uploads"
docker compose -f "$COMPOSE_FILE" exec -T ctfd \
  tar -C /var/uploads -cf - . > "$workdir/uploads.tar"

# 3. Elasticsearch: trigger a flush so on-disk segments are consistent, then
#    archive the data volume. Avoids running snapshots via the ES API to keep
#    the script dependency-free.
echo "  - flushing elasticsearch"
docker compose -f "$COMPOSE_FILE" exec -T elasticsearch \
  curl -s -X POST "http://localhost:9200/_flush?wait_if_ongoing=true" >/dev/null
echo "  - archiving elasticsearch data volume"
docker compose -f "$COMPOSE_FILE" exec -T elasticsearch \
  tar -C /usr/share/elasticsearch/data -cf - . > "$workdir/elasticsearch.tar"

# 4. Include env so restore is self-contained (chmod 600 on extract).
cp "$ENV_FILE" "$workdir/.env.production"

# 5. Pack everything (zip preserves cross-platform portability).
(cd "$workdir" && zip -q -r "$archive" .)

# 6. Rotate older backups beyond RETENTION_DAYS.
find "$BACKUP_DIR" -maxdepth 1 -name 'hikari-*.zip' -mtime +"$RETENTION_DAYS" -delete

size=$(du -h "$archive" | cut -f1)
echo "backup complete: $archive ($size)"
