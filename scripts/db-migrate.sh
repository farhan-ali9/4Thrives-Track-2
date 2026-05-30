#!/usr/bin/env bash
set -euo pipefail

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:5433/conversion_coach}"
export CHECKPOINT_DISABLE="${CHECKPOINT_DISABLE:-1}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/uniqa-conversion-coach-cache}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/tmp/uniqa-conversion-coach-config}"
npm run db:deploy --workspace coach-api
