#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_daily_tail.sh <CHAIN_ID> <TIP_BLOCK>
# Backfills last $REORG_WINDOW blocks ending at TIP_BLOCK (e.g., your node's latest)
CHAIN_ID="${1:-}"
TIP_BLOCK="${2:-}"

if [[ -z "${CHAIN_ID}" || -z "${TIP_BLOCK}" ]]; then
  echo "Usage: $0 <CHAIN_ID> <TIP_BLOCK>"
  exit 1
fi

if [[ -f ".env" ]]; then source .env; fi
: "${REORG_WINDOW:?REORG_WINDOW not set}"

FROM_BLOCK="$(( TIP_BLOCK - REORG_WINDOW ))"
if (( FROM_BLOCK < 0 )); then FROM_BLOCK=0; fi

./run_window.sh "${CHAIN_ID}" "${FROM_BLOCK}" "${TIP_BLOCK}"