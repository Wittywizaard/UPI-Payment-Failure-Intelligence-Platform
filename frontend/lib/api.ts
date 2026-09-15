const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "upi_fip_token";

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface ApiFetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

function buildQueryString(params?: ApiFetchOptions["params"]): string {
  if (!params) return "";
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { params, ...init } = options;
  const token = getToken();

  const res = await fetch(`${API_BASE}${path}${buildQueryString(params)}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "UNAUTHORIZED", "Session expired. Please sign in again.");
  }

  if (!res.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `Request failed with status ${res.status}`;
    let requestId: string | undefined;
    try {
      const body = await res.json();
      code = body?.detail?.error?.code || body?.error?.code || code;
      message = body?.detail?.error?.message || body?.error?.message || message;
      requestId = body?.detail?.error?.request_id;
    } catch {
      // response wasn't JSON; keep defaults
    }
    throw new ApiError(res.status, code, message, requestId);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, params?: ApiFetchOptions["params"]) =>
    apiFetch<T>(path, { method: "GET", params }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};

export { API_BASE };
