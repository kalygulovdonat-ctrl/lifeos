#!/usr/bin/env sh
# PostgreSQL backup (SDD §11.4). Usage: infra/scripts/backup.sh [output_dir]
# Runs pg_dump inside the db container of the production stack and writes a
# timestamped custom-format dump. Encrypt and upload it with your storage tooling.
set -eu

OUT_DIR="${1:-./backups}"
COMPOSE="docker compose -f infra/compose/docker-compose.prod.yml"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"

$COMPOSE exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$OUT_DIR/lifeos-$STAMP.dump"
echo "Backup written to $OUT_DIR/lifeos-$STAMP.dump"
