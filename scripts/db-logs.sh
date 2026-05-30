#!/usr/bin/env bash
set -euo pipefail

docker compose logs coach-db "${@:-}"
