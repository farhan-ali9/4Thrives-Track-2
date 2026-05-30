#!/usr/bin/env bash
set -euo pipefail

docker compose up -d coach-db
docker compose ps coach-db
