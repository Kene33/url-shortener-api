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

export interface ProfileResponse {
  user: User;
  preferences: Preferences;
}
