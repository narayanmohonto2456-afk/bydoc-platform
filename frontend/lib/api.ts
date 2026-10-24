export type Account = {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
};

export type PatientProfile = {
  first_name: string;
  last_name: string;
  phone_number: string | null;
  date_of_birth: string | null;
  gender: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
};

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function requestUrl(path: string): string {
  const base = new URL(apiBase);
  // Local cookies must stay on the same site, whether opened via localhost or IPv4.
  if (process.env.NODE_ENV === "development" && typeof window !== "undefined"
    && ["localhost", "127.0.0.1"].includes(base.hostname)
    && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    base.hostname = window.location.hostname;
  }
  return `${base.toString().replace(/\/$/, "")}${path}`;
}

export function administrationUrl(): string {
  return new URL("/admin/", apiBase).toString();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(data: unknown): string {
  if (!data || typeof data !== "object") return "Something went wrong. Please try again.";
  const fields = data as Record<string, unknown>;
  if (typeof fields.detail === "string") return fields.detail;
  for (const [field, value] of Object.entries(fields)) {
    const first = Array.isArray(value) ? value[0] : value;
    if (typeof first === "string") return `${field.replaceAll("_", " ")}: ${first}`;
  }
  return "Please check your details and try again.";
}

async function csrfToken(): Promise<string> {
  const response = await fetch(requestUrl("/auth/csrf/"), {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status, "Could not start a secure session. Please try again.");
  const data = (await response.json()) as { csrf_token: string };
  return data.csrf_token;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refreshOnce = async () => {
    // Another tab may have refreshed while this request was waiting for the lock.
    const current = await fetch(requestUrl("/auth/me/"), { credentials: "include", cache: "no-store" });
    if (current.ok) return true;
    const headers = new Headers({ "X-CSRFToken": await csrfToken() });
    const refreshed = await fetch(requestUrl("/auth/token/refresh/"), {
      method: "POST", headers, credentials: "include", cache: "no-store",
    });
    return refreshed.ok;
  };

  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("bydoc-auth-refresh", refreshOnce);
  }
  return refreshOnce();
}

function sharedRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = refreshSession().finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers.set("X-CSRFToken", await csrfToken());
    }
    const request: RequestInit = {
      ...init,
      method,
      headers,
      credentials: "include",
      cache: "no-store",
    };
    response = await fetch(requestUrl(path), request);
    if (response.status === 401 && !path.startsWith("/auth/token/")
      && !["/auth/login/", "/auth/google/"].includes(path)) {
      if (await sharedRefresh()) response = await fetch(requestUrl(path), request);
    }
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    throw new ApiError(0, "Cannot reach BYdoc right now. Please try again.");
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(data));
  return data as T;
}

export function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return apiRequest<T>(path, { method: "POST", body: JSON.stringify(body) });
}
