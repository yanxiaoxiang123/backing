/**
 * Lightweight logger abstraction.
 * Swap the implementation (e.g. to a remote service) by editing the single
 * `_log` helper below; no call-sites need to change.
 */

type LogLevel = "debug" | "info" | "warn" | "error";

const ENABLED_LEVELS: Record<LogLevel, boolean> = {
  debug: import.meta.env.DEV ?? true,
  info: true,
  warn: true,
  error: true,
};

function _log(level: LogLevel, ...args: unknown[]): void {
  if (!ENABLED_LEVELS[level]) return;

  switch (level) {
    case "error":
      console.error(...args);
      break;
    case "warn":
      console.warn(...args);
      break;
    case "info":
      console.info(...args);
      break;
    case "debug":
      console.debug(...args);
      break;
  }
}

export const logger = {
  debug: (...args: unknown[]) => _log("debug", ...args),
  info: (...args: unknown[]) => _log("info", ...args),
  warn: (...args: unknown[]) => _log("warn", ...args),
  error: (...args: unknown[]) => _log("error", ...args),
};