import type {
  ActionMessageResponse,
  AnalyticsPeriod,
  AnalyticsResponse,
  ApiErrorPayload,
  CreateLinkPayload,
  CreateLinkResponse,
  ExportResponse,
  Folder,
  FolderColor,
  LinkListResponse,
  NotificationItem,
  NotificationListResponse,
  Preferences,
  ProfileResponse,
  RegisterResponse,
  SessionResponse,
  TwoFactorChallengeResponse,
  UpdateLinkPayload,
  User,
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
let refreshHandler: (() => Promise<string | null>) | null = null;
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
  if (response.status === 204) return undefined as T;
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
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retryOnUnauthorized) {
    const nextToken = await refreshAccessToken();
    if (nextToken) return apiRequest<T>(path, init, false);
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
  loginWithTwoFactor: (payload: { login_token: string; code: string }) =>
    apiRequest<SessionResponse>("/api/v1/auth/2fa/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  register: (payload: { email: string; password: string }) =>
    apiRequest<RegisterResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refresh: () => apiRequest<SessionResponse>("/api/v1/auth/refresh", { method: "POST" }, false),
  logout: () => apiRequest<ActionMessageResponse>("/api/v1/auth/logout", { method: "POST" }),
  verifyEmail: (token: string) =>
    apiRequest<User>("/api/v1/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
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
  me: () => apiRequest<User>("/api/v1/me"),
  getPreferences: () => apiRequest<Preferences>("/api/v1/me/preferences"),
  getProfile: async (): Promise<ProfileResponse> => {
    const [user, preferences] = await Promise.all([api.me(), api.getPreferences()]);
    return { user, preferences };
  },
  updateProfile: (payload: Partial<{ display_name: string; email: string }>) =>
    apiRequest<User>("/api/v1/me/profile", { method: "PATCH", body: JSON.stringify(payload) }),
  uploadAvatar: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return apiRequest<User>("/api/v1/me/avatar", { method: "POST", body: data });
  },
  deleteAvatar: () => apiRequest<User>("/api/v1/me/avatar", { method: "DELETE" }),
  updatePreferences: (payload: Partial<Pick<Preferences, "theme" | "language" | "email_notifications" | "system_notifications">>) =>
    apiRequest<Preferences>("/api/v1/me/preferences", { method: "PATCH", body: JSON.stringify(payload) }),
  createLink: (payload: CreateLinkPayload) =>
    apiRequest<CreateLinkResponse>("/api/v1/links", { method: "POST", body: JSON.stringify(payload) }),
  getLinks: (params: URLSearchParams) => apiRequest<LinkListResponse>(`/api/v1/me/links?${params.toString()}`),
  updateLink: (shortcode: string, payload: UpdateLinkPayload) =>
    apiRequest(`/api/v1/me/links/${shortcode}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getFolders: () => apiRequest<Folder[]>("/api/v1/me/folders"),
  createFolder: (payload: { name: string; color: FolderColor }) =>
    apiRequest<Folder>("/api/v1/me/folders", { method: "POST", body: JSON.stringify(payload) }),
  updateFolder: (id: number, payload: Partial<{ name: string; color: FolderColor }>) =>
    apiRequest<Folder>(`/api/v1/me/folders/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteFolder: (id: number) => apiRequest<void>(`/api/v1/me/folders/${id}`, { method: "DELETE" }),
  getAnalytics: (period: AnalyticsPeriod, timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC") =>
    apiRequest<AnalyticsResponse>(`/api/v1/me/analytics?period=${period}&timezone=${encodeURIComponent(timezone)}`),
  getNotifications: () => apiRequest<NotificationListResponse>("/api/v1/me/notifications"),
  readNotification: (id: number) =>
    apiRequest<NotificationItem>(`/api/v1/me/notifications/${id}/read`, { method: "PATCH" }),
  readAllNotifications: () => apiRequest<ActionMessageResponse>("/api/v1/me/notifications/read-all", { method: "POST" }),
  changePassword: (payload: { current_password: string; new_password: string }) =>
    apiRequest<ActionMessageResponse>("/api/v1/me/change-password", { method: "POST", body: JSON.stringify(payload) }),
  requestEnableTwoFactor: () =>
    apiRequest<ActionMessageResponse>("/api/v1/me/2fa/email/request-enable", { method: "POST" }),
  confirmEnableTwoFactor: (code: string) =>
    apiRequest<{ enabled: boolean }>("/api/v1/me/2fa/email/confirm-enable", { method: "POST", body: JSON.stringify({ code }) }),
  disableTwoFactor: () => apiRequest<{ enabled: boolean }>("/api/v1/me/2fa/email/disable", { method: "POST" }),
  exportData: () => apiRequest<ExportResponse>("/api/v1/me/export"),
  deleteAccount: (password: string) =>
    apiRequest<ActionMessageResponse>("/api/v1/me", { method: "DELETE", body: JSON.stringify({ password }) }),
};
