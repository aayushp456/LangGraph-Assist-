import { fetchWithTimeout, getApiUrl } from "@/lib/runtime-config";
import { getAuthToken } from "@/hooks/useAuth";

/**
 * Fetch wrapper that auto-attaches the Authorization header.
 */
export async function authFetch(
  path: string,
  options: RequestInit = {},
  timeout = 10000,
): Promise<Response> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetchWithTimeout(
    path.startsWith("http") ? path : `${getApiUrl()}${path}`,
    { ...options, headers },
    timeout,
  );
}
