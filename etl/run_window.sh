#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_window.sh <CHAIN_ID> <FROM_BLOCK> <TO_BLOCK>
# Example: ./run_window.sh 42161 23200000 23201000
#          ./run_window.sh 14 48200000 48200250

CHAIN_ID="${1:-}"
FROM_BLOCK="${2:-}"
TO_BLOCK="${3:-}"

if [[ -z "${CHAIN_ID}" || -z "${FROM_BLOCK}" || -z "${TO_BLOCK}" ]]; then
  echo "Usage: $0 <CHAIN_ID> <FROM_BLOCK> <TO_BLOCK>"
  exit 1
fi

# Load .env if present
if [[ -f ".env" ]]; then source .env; fi
: "${PGURL:?PGURL not set. Export PGURL or create .env.}"
PSQL="${PSQL_BIN:-psql}"

run_sql () {
  local file="$1"
  shift
  "${PSQL}" "${PGURL}" -v ON_ERROR_STOP=1 \
    -v CHAIN_ID="${CHAIN_ID}" -v FROM_BLOCK="${FROM_BLOCK}" -v TO_BLOCK="${TO_BLOCK}" "$@" -f "${file}"
}

echo ">> Initializing schemas & helpers"
run_sql sql/00_init_schemas.sql
run_sql sql/10_amount_scaling_helpers.sql

echo ">> Ensuring chains are seeded"
run_sql sql/02_seed_chains.sql

case "${CHAIN_ID}" in
  42161)
    echo ">> Seeding Arbitrum contracts (edit 03_seed_contracts_arbitrum.sql to add/verify addresses)"
    run_sql sql/03_seed_contracts_arbitrum.sql
    echo ">> Running Arbitrum ETLs (OpenOcean, Aave v3, PancakeSwap)"
    run_sql sql/04_etl_openocean.sql
    run_sql sql/06_etl_aave_v3.sql
    run_sql sql/08_etl_pancakeswap.sql
    ;;
  14)
    echo ">> Seeding Flare contracts (edit 03_seed_contracts_flare.sql to add/verify addresses)"
    run_sql sql/03_seed_contracts_flare.sql
    echo ">> Running Flare ETLs (SparkDEX v3, Kinetic, FTSOv2)"
    run_sql sql/05_etl_sparkdex_v3.sql
    run_sql sql/07_etl_kinetic.sql
    run_sql sql/09_etl_ftso.sql
    ;;
  *)
    echo "Unsupported CHAIN_ID: ${CHAIN_ID}"
    exit 2
    ;;
esac

echo ">> DONE: CHAIN_ID=${CHAIN_ID} blocks [${FROM_BLOCK}, ${TO_BLOCK}]"