#!/usr/bin/env bash

leonardo_load_env() {
  if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$LEONARDO_ENV_FILE"
    set +a
  fi
}

leonardo_prepare_pixi_cache() {
  if [[ -n "${PIXI_CACHE_DIR:-}" ]]; then
    mkdir -p "$PIXI_CACHE_DIR"
    return
  fi

  local scratch_candidate="/scratch_local/pixi-cache-${USER}"
  local tmp_candidate="/tmp/pixi-cache-${USER}"

  if mkdir -p "$scratch_candidate" 2>/dev/null; then
    export PIXI_CACHE_DIR="$scratch_candidate"
    return
  fi

  mkdir -p "$tmp_candidate"
  export PIXI_CACHE_DIR="$tmp_candidate"
}
