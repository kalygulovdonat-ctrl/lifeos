#!/usr/bin/env sh
# Restore a dump produced by backup.sh into the production db container.
# Usage: infra/scripts/restore.sh path/to/lifeos-YYYYmmddTHHMMSSZ.dump
# WARNING: --clean drops existing objects in the target database before restoring.
set -eu

DUMP="${1:?usage: restore.sh <dump-file>}"
COMPOSE="docker compose -f infra/compose/docker-compose.prod.yml"

printf "Restore %s into the production database? Type 'restore' to continue: " "$DUMP"
read -r answer
[ "$answer" = "restore" ] || { echo "Aborted."; exit 1; }

$COMPOSE exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP"
echo "Restore complete."
