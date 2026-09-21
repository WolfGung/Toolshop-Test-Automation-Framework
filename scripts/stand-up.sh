#!/usr/bin/env bash
# scripts/stand-up.sh — bring up a disposable Toolshop and seed it.
set -euo pipefail

COMPOSE="docker compose -f docker-compose.stand.yml"
API_URL="${API_BASE_URL:-http://localhost:8091}"
UI_URL="${BASE_URL:-http://localhost:4200}"

fail() {              # fail <message> <service...> — dumps every named service's tail
  local message="$1"; shift
  echo "stand-up: $message" >&2
  local service
  for service in "$@"; do
    echo "--- last 40 lines of $service ---" >&2
    $COMPOSE logs --tail 40 "$service" >&2 || true
  done
  exit 1
}

wait_for() {          # wait_for <seconds> <service(s), space-separated> <message> <command...>
  local deadline=$(( SECONDS + $1 )); local services="$2"; local message="$3"; shift 3
  until "$@" >/dev/null 2>&1; do
    # Intentionally unquoted: a caller that names two services ("web laravel-api")
    # relies on word-splitting here to hand fail() two separate arguments.
    # shellcheck disable=SC2086
    (( SECONDS < deadline )) || fail "$message" $services
    sleep 2
  done
}

$COMPOSE up -d

echo "stand-up: waiting for the database"
wait_for 120 mariadb "the database never accepted a connection" \
  $COMPOSE exec -T mariadb mysqladmin ping -uroot -proot

echo "stand-up: waiting for the API process"
wait_for 180 "web laravel-api" "the API never answered on $API_URL" \
  curl -sf -o /dev/null "$API_URL/status"

echo "stand-up: seeding the database"
$COMPOSE exec -T laravel-api php artisan migrate:fresh --seed --force \
  || fail "the seeder failed" laravel-api

echo "stand-up: waiting for the catalogue"
wait_for 60 "web laravel-api" "the API never served products after seeding" \
  curl -sf -o /dev/null "$API_URL/products"

echo "stand-up: waiting for the storefront (ng serve compiles on start)"
wait_for 420 angular-ui "the storefront never rendered on $UI_URL" \
  curl -sf -o /dev/null "$UI_URL"

echo "stand-up: ready — UI $UI_URL, API $API_URL"
