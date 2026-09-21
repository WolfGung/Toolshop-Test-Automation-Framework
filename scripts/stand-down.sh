#!/usr/bin/env bash
# scripts/stand-down.sh — remove the stand and its data.
set -euo pipefail
docker compose -f docker-compose.stand.yml down -v --remove-orphans
