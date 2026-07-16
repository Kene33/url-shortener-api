import type {
  ActionMessageResponse,
  ApiErrorPayload,
  CreateLinkPayload,
  CreateLinkResponse,
  ExportResponse,
  FolderListResponse,
  LinkListResponse,
  NotificationListResponse,
  Preferences,
  ProfileResponse,
  RegisterResponse,
  SessionResponse,
  TwoFactorChallengeResponse,
  UpdateLinkPayload,
} from "@/api/types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, payload?: ApiErrorPayload) {
    super(payload?.detail ?? `Request failed with status ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

type SessionGetter = () => string | null;
type SessionSetter = (token: string | null) => void;

let getAccessToken: SessionGetter = () => null;
let setAccessToken: SessionSetter = () => undefined;
let refreshHandler: null | (() => Promise<string | null>) = null;
let refreshInFlight: Promise<string | null> | null = null;

export function configureApiAuth(options: {
  getToken: SessionGetter;
  setToken: SessionSetter;
  refresh: () => Promise<string | null>;
}) {
  getAccessToken = options.getToken;
  setAccessToken = options.setToken;
  refreshHandler = options.refresh;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function refreshAccessToken() {
  if (!refreshHandler) return null;
  if (!refreshInFlight) {
    refreshInFlight = refreshHandler().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  retryOnUnauthorized = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && retryOnUnauthorized) {
    const nextToken = await refreshAccessToken();
    if (nextToken) {
      setAccessToken(nextToken);
      return apiRequest<T>(path, init, false);
    }
    setAccessToken(null);
  }

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = undefined;
    }
    throw new ApiError(response.status, payload);
  }

  return parseResponse<T>(response);
}

export const api = {
  login: (payload: { email: string; password: string }) =>
    apiRequest<SessionResponse | TwoFactorChallengeResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  loginWithTwoFactor: (payload: { challenge_token: string; code: string }) =>
    apiRequest<SessionResponse>("/api/v1/auth/verify-2fa", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  register: (payload: { email: string; password: string }) =>
    apiRequest<RegisterResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refresh: () =>
    apiRequest<SessionResponse>("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({}),
    }, false),
  logout: () =>
    apiRequest<ActionMessageResponse>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  verifyEmail: (token: string) =>
    apiRequest("/api/v1/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  requestPasswordReset: (email: string) =>
    apiRequest<ActionMessageResponse>("/api/v1/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (payload: { token: string; new_password: string }) =>
    apiRequest<ActionMessageResponse>("/api/v1/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  me: () => apiRequest<ProfileResponse>("/api/v1/me/profile"),
  updateProfile: (payload: Partial<{ display_name: string; email: string }>) =>
    apiRequest<ProfileResponse>("/api/v1/me/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  uploadAvatar: (file: File) => {
    const data = new FormData();
    data.append("avatar", file);
    return apiRequest<ProfileResponse>("/api/v1/me/profile/avatar", {
      method: "POST",
      body: data,
    });
  },
  deleteAvatar: () =>
    apiRequest<ProfileResponse>("/api/v1/me/profile/avatar", {
      method: "DELETE",
    }),
  updatePreferences: (payload: Partial<Preferences>) =>
    apiRequest<Preferences>("/api/v1/me/preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createLink: (payload: CreateLinkPayload) =>
    apiRequest<CreateLinkResponse>("/api/v1/links", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getLinks: (params: URLSearchParams) =>
    apiRequest<LinkListResponse>(`/api/v1/me/links?${params.toString()}`),
  updateLink: (shortcode: string, payload: UpdateLinkPayload) =>
    apiRequest(`/api/v1/me/links/${shortcode}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getFolders: () => apiRequest<FolderListResponse>("/api/v1/me/folders"),
  createFolder: (payload: { name: string; color: string }) =>
    apiRequest("/api/v1/me/folders", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  renameFolder: (id: string, payload: { name: string; color: string }) =>
    apiRequest(`/api/v1/me/folders/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteFolder: (id: string) =>
    apiRequest(`/api/v1/me/folders/${id}`, { method: "DELETE" }),
  getAnalytics: (period: string) =>
    apiRequest(`/api/v1/me/analytics?period=${period}`),
  getNotifications: () =>
    apiRequest<NotificationListResponse>("/api/v1/me/notifications"),
  readNotification: (id: string) =>
    apiRequest(`/api/v1/me/notifications/${id}/read`, { method: "POST" }),
  readAllNotifications: () =>
    apiRequest("/api/v1/me/notifications/read-all", { method: "POST" }),
  changePassword: (payload: {
    current_password: string;
    new_password: string;
  }) =>
    apiRequest<ActionMessageResponse>("/api/v1/me/change-password", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  toggleTwoFactor: (enabled: boolean, code?: string) =>
    apiRequest<{ enabled: boolean; debug_code?: string | null }>(
      "/api/v1/me/two-factor",
      {
        method: "POST",
        body: JSON.stringify({ enabled, code }),
      },
    ),
  exportData: () => apiRequest<ExportResponse>("/api/v1/me/export"),
  deleteAccount: (password: string) =>
    apiRequest<ActionMessageResponse>("/api/v1/me/delete-account", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
};
