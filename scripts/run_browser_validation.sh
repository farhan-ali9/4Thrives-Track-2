#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
	# shellcheck disable=SC1090
	set -a
	source "$LEONARDO_ENV_FILE"
	set +a
fi
python browser-runner/run_batch.py --mode validation --sessions "${RUNNER_SESSIONS:-3}" --experiment-id "validation-$(date +%Y%m%d-%H%M%S)"
