const PREFIX = "[UNIQA Coach]";

type LogData = Record<string, unknown> | unknown[] | undefined;

interface DebugWindow {
  __UNIQA_COACH_DEBUG__?: boolean;
}

/**
 * Verbose debug logging is enabled by default so the coach pipeline is easy to
 * diagnose during the hackathon. Set `globalThis.__UNIQA_COACH_DEBUG__ = false`
 * (in the page console or the service-worker console) to silence debug lines.
 * Info/warn/error are always emitted.
 */
function debugEnabled(): boolean {
  return (globalThis as DebugWindow).__UNIQA_COACH_DEBUG__ !== false;
}

function format(scope: string, message: string): string {
  return `${PREFIX} [${scope}] ${message}`;
}

export interface ScopedLogger {
  debug(message: string, data?: LogData): void;
  info(message: string, data?: LogData): void;
  warn(message: string, data?: LogData): void;
  error(message: string, data?: LogData): void;
}

export function createLogger(scope: string): ScopedLogger {
  return {
    debug(message, data) {
      if (!debugEnabled()) {
        return;
      }
      if (data === undefined) {
        console.debug(format(scope, message));
      } else {
        console.debug(format(scope, message), data);
      }
    },
    info(message, data) {
      if (data === undefined) {
        console.info(format(scope, message));
      } else {
        console.info(format(scope, message), data);
      }
    },
    warn(message, data) {
      if (data === undefined) {
        console.warn(format(scope, message));
      } else {
        console.warn(format(scope, message), data);
      }
    },
    error(message, data) {
      if (data === undefined) {
        console.error(format(scope, message));
      } else {
        console.error(format(scope, message), data);
      }
    },
  };
}
