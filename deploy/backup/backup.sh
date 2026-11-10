#!/bin/bash
set -euo pipefail
umask 077

backup_dir=/var/lib/survey-ebt-backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$backup_dir/survey_ebt_${stamp}.dump"
temp=$(mktemp "$backup_dir/.survey_ebt.XXXXXX")
trap 'rm -f -- "$temp"' EXIT

pg_dump -Fc -d survey_ebt > "$temp"
pg_restore --list "$temp" >/dev/null
mv -- "$temp" "$archive"
printf 'Saved %s\n' "$archive"
