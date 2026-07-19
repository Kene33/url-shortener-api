import type { components } from "@/api/generated";

export type ApiErrorPayload = {
  code: string;
  detail: string;
  errors?: Array<{ loc: Array<string | number>; msg: string; type: string }>;
};

export type ApiSchema = components["schemas"];
export type User = ApiSchema["UserResponse"];
export type SessionResponse = ApiSchema["TokenResponse"];
export type TwoFactorChallengeResponse = ApiSchema["LoginChallengeResponse"];
export type RegisterResponse = ApiSchema["RegisterResponse"];
export type ActionMessageResponse = ApiSchema["ActionMessageResponse"];
export type StoredTheme = ApiSchema["PreferencesResponse"]["theme"];
export type ThemePreference = StoredTheme | "system";
export type Language = ApiSchema["PreferencesResponse"]["language"];
export type Preferences = ApiSchema["PreferencesResponse"];
export type LinkMode = ApiSchema["CreateLinkRequest"]["mode"];
export type LinkSort = "created_at_desc" | "created_at_asc" | "access_count_desc" | "access_count_asc";
export type AnalyticsPeriod = "24h" | "7d" | "30d" | "90d";
export type LinkItem = ApiSchema["LinkResponse"];
export type LinkListResponse = ApiSchema["LinkListResponse"];
export type CreateLinkPayload = ApiSchema["CreateLinkRequest"];
export type CreateLinkResponse = ApiSchema["CreateLinkResponse"];
export type UpdateLinkPayload = ApiSchema["UpdateLinkRequest"];
export type Folder = ApiSchema["FolderResponse"];
export type FolderColor = ApiSchema["FolderResponse"]["color"];
export type AnalyticsResponse = ApiSchema["AnalyticsResponse"];
export type NotificationItem = ApiSchema["NotificationResponse"];
export type NotificationListResponse = ApiSchema["NotificationListResponse"];
export type ExportResponse = ApiSchema["ExportResponse"];
export type AdminUserListResponse = ApiSchema["AdminUserListResponse"];
export type AdminUserUpdatePayload = ApiSchema["AdminUserUpdateRequest"];
export type AdminLinkItem = ApiSchema["AdminLinkResponse"];
export type AdminLinkListResponse = ApiSchema["AdminLinkListResponse"];
export type AdminLinkUpdatePayload = ApiSchema["AdminLinkUpdateRequest"];
export type DashboardResponse = ApiSchema["DashboardResponse"];
export type ReportItem = ApiSchema["ReportResponse"];
export type ReportListResponse = ApiSchema["ReportListResponse"];
export type ReportResolvePayload = ApiSchema["ReportResolveRequest"];
export type AuditEvent = ApiSchema["AuditEventResponse"];
export type AuditLogResponse = ApiSchema["AuditLogResponse"];
export type RetentionSettingsResponse = ApiSchema["RetentionSettingsResponse"];
export type RetentionSettingsUpdatePayload = ApiSchema["RetentionSettingsUpdateRequest"];
export type ModerationCategory = NonNullable<AdminLinkUpdatePayload["category"]>;
export type ReportStatus = ReportItem["status"];
export type StaffRole = Extract<User["role"], "support" | "moderator" | "admin">;
export type ProfileUpdateResponse = ApiSchema["ProfileUpdateResponse"];

export interface ProfileResponse {
  user: User;
  preferences: Preferences;
}
