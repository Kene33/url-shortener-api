import type {
  ActionMessageResponse,
  AdminLinkListResponse,
  AuditLogResponse,
  AdminLinkUpdatePayload,
  AdminUserListResponse,
  AdminUserUpdatePayload,
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
  ProfileUpdateResponse,
  ReportListResponse,
  ReportResolvePayload,
  RegisterResponse,
  RetentionSettingsResponse,
  RetentionSettingsUpdatePayload,
  SessionResponse,
  TwoFactorChallengeResponse,
  UpdateLinkPayload,
  User,
  DashboardResponse,
} from "@/api/types";
import i18n from "@/i18n";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, payload?: ApiErrorPayload, message?: string) {
    super(message ?? payload?.detail ?? i18n.t("errors.httpStatus", { status }));
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

function getValidationField(loc?: Array<string | number>) {
  const field = loc?.[loc.length - 1];
  if (typeof field !== "string") {
    return i18n.t("common.notSet");
  }
  return i18n.t(`errors.field.${field}`, { defaultValue: field });
}

function getApiErrorMessage(status: number, payload?: ApiErrorPayload) {
  if (payload?.code) {
    const key = `errors.code.${payload.code}`;
    if (i18n.exists(key)) {
      return i18n.t(key);
    }
  }
  if (payload?.errors?.length) {
    return i18n.t("errors.validation", {
      field: getValidationField(payload.errors[0].loc),
    });
  }
  if (payload?.detail) {
    return payload.detail;
  }
  return i18n.t("errors.httpStatus", { status });
}

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
    throw new ApiError(response.status, payload, getApiErrorMessage(response.status, payload));
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
    apiRequest<ProfileUpdateResponse>("/api/v1/me/profile", { method: "PATCH", body: JSON.stringify(payload) }),
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
  getAdminDashboard: () => apiRequest<DashboardResponse>("/api/v1/admin/dashboard"),
  getAdminUsers: (params: {
    q?: string;
    role?: User["role"];
    is_active?: boolean;
    limit: number;
    offset: number;
  }) => {
    const search = new URLSearchParams({
      limit: String(params.limit),
      offset: String(params.offset),
    });
    if (params.q) search.set("q", params.q);
    if (params.role) search.set("role", params.role);
    if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
    return apiRequest<AdminUserListResponse>(`/api/v1/admin/users?${search.toString()}`);
  },
  updateAdminUser: (userId: number, payload: AdminUserUpdatePayload) =>
    apiRequest<User>(`/api/v1/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getAdminLinks: (params: { owner_id?: string; is_active?: boolean; limit: number; offset: number }) => {
    const search = new URLSearchParams({
      limit: String(params.limit),
      offset: String(params.offset),
    });
    if (params.owner_id) search.set("owner_id", params.owner_id);
    if (typeof params.is_active === "boolean") search.set("is_active", String(params.is_active));
    return apiRequest<AdminLinkListResponse>(`/api/v1/admin/links?${search.toString()}`);
  },
  updateAdminLink: (shortcode: string, payload: AdminLinkUpdatePayload) =>
    apiRequest(`/api/v1/admin/links/${shortcode}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getAdminReports: (params: {
    status_filter?: ReportResolvePayload["status"];
    category?: AdminLinkUpdatePayload["category"];
    limit: number;
    offset: number;
  }) => {
    const search = new URLSearchParams({
      limit: String(params.limit),
      offset: String(params.offset),
    });
    if (params.status_filter) search.set("status_filter", params.status_filter);
    if (params.category) search.set("category", params.category);
    return apiRequest<ReportListResponse>(`/api/v1/admin/reports?${search.toString()}`);
  },
  updateAdminReport: (reportId: number, payload: ReportResolvePayload) =>
    apiRequest(`/api/v1/admin/reports/${reportId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getAdminAuditLog: (params: {
    actor_id?: string;
    action?: string;
    object_type?: string;
    date_from?: string;
    date_to?: string;
    limit: number;
    offset: number;
  }) => {
    const search = new URLSearchParams({
      limit: String(params.limit),
      offset: String(params.offset),
    });
    if (params.actor_id) search.set("actor_id", params.actor_id);
    if (params.action) search.set("action", params.action);
    if (params.object_type) search.set("object_type", params.object_type);
    if (params.date_from) search.set("date_from", params.date_from);
    if (params.date_to) search.set("date_to", params.date_to);
    return apiRequest<AuditLogResponse>(`/api/v1/admin/audit-log?${search.toString()}`);
  },
  getAdminRetentionSettings: () => apiRequest<RetentionSettingsResponse>("/api/v1/admin/settings/retention"),
  updateAdminRetentionSettings: (payload: RetentionSettingsUpdatePayload) =>
    apiRequest<RetentionSettingsResponse>("/api/v1/admin/settings/retention", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};
