#!/usr/bin/env bash

leonardo_preserve_overrides() {
  local key
  for key in \
    EXPERIMENT_ID \
    RUNNER_EXECUTION_MODE \
    RUNNER_SESSIONS \
    RUNNER_SESSIONS_PER_MODE \
    RUNNER_MODE \
    RUNNER_OUTPUT_DIR \
    PIXI_CACHE_DIR \
    VLLM_SERVE_CMD \
    VLLM_BOOT_WAIT_S \
    HTTP_PROXY \
    HTTPS_PROXY \
    http_proxy \
    https_proxy
  do
    if [[ -n "${!key+x}" ]]; then
      export "LEONARDO_PRESERVE_${key}=${!key}"
    fi
  done
}

leonardo_restore_overrides() {
  local key preserved_key
  for key in \
    EXPERIMENT_ID \
    RUNNER_EXECUTION_MODE \
    RUNNER_SESSIONS \
    RUNNER_SESSIONS_PER_MODE \
    RUNNER_MODE \
    RUNNER_OUTPUT_DIR \
    PIXI_CACHE_DIR \
    VLLM_SERVE_CMD \
    VLLM_BOOT_WAIT_S \
    HTTP_PROXY \
    HTTPS_PROXY \
    http_proxy \
    https_proxy
  do
    preserved_key="LEONARDO_PRESERVE_${key}"
    if [[ -n "${!preserved_key+x}" ]]; then
      export "${key}=${!preserved_key}"
      unset "$preserved_key"
    fi
  done
}

leonardo_export_proxy() {
  local proxy_url="${LEONARDO_PROXY_URL:-}"
  if [[ -n "$proxy_url" ]]; then
    : "${HTTP_PROXY:=$proxy_url}"
    : "${HTTPS_PROXY:=$proxy_url}"
    : "${http_proxy:=$proxy_url}"
    : "${https_proxy:=$proxy_url}"
  fi

  if [[ -n "${HTTP_PROXY:-}" && -z "${http_proxy:-}" ]]; then
    export http_proxy="$HTTP_PROXY"
  fi
  if [[ -n "${HTTPS_PROXY:-}" && -z "${https_proxy:-}" ]]; then
    export https_proxy="$HTTPS_PROXY"
  fi
  if [[ -n "${http_proxy:-}" && -z "${HTTP_PROXY:-}" ]]; then
    export HTTP_PROXY="$http_proxy"
  fi
  if [[ -n "${https_proxy:-}" && -z "${HTTPS_PROXY:-}" ]]; then
    export HTTPS_PROXY="$https_proxy"
  fi
}

leonardo_load_env() {
  leonardo_preserve_overrides
  if [[ -n "${LEONARDO_ENV_FILE:-}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$LEONARDO_ENV_FILE"
    set +a
  fi
  leonardo_restore_overrides
  leonardo_export_proxy
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
