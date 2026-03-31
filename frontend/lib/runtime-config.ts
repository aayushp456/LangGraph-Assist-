const DEFAULT_BACKEND_PORT =
  process.env.NEXT_PUBLIC_BACKEND_PORT?.trim() || "8000";

function getRuntimeHost() {
  if (typeof window === "undefined") {
    return "127.0.0.1";
  }

  const hostname = window.location.hostname?.trim();
  if (!hostname || hostname === "localhost") {
    return "127.0.0.1";
  }

  return hostname;
}

export function getApiUrl() {
  const configured = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const protocol =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "https:"
      : "http:";

  return `${protocol}//${getRuntimeHost()}:${DEFAULT_BACKEND_PORT}`;
}

export function getWebSocketUrl() {
  const configured = process.env.NEXT_PUBLIC_WS_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const protocol =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "wss:"
      : "ws:";

  return `${protocol}//${getRuntimeHost()}:${DEFAULT_BACKEND_PORT}/ws`;
}

export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = 10000
) {
  const controller = new AbortController();
  const timeoutError = new DOMException(
    `Request timed out after ${timeoutMs}ms`,
    "TimeoutError"
  );
  const timeoutId = setTimeout(() => controller.abort(timeoutError), timeoutMs);

  const signal = init.signal
    ? AbortSignal.any([init.signal, controller.signal])
    : controller.signal;

  try {
    return await fetch(input, {
      ...init,
      signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
}
