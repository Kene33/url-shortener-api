export type ThemePreference = "light" | "dark" | "system";
export type Language = "ru" | "en";
export type LinkMode = "reuse" | "new";
export type LinkSort =
  | "created_at_desc"
  | "created_at_asc"
  | "clicks_desc"
  | "clicks_asc"
  | "label_asc";
export type AnalyticsPeriod = "24h" | "7d" | "30d" | "90d";
export type UserRole = "user" | "admin";
export type UserStatus = "active" | "pending" | "disabled";

export interface ApiErrorPayload {
  code: string;
  detail: string;
  errors?: Array<{ loc: Array<string | number>; msg: string; type: string }>;
}

export interface User {
  id: number;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  is_admin: boolean;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  role?: UserRole;
  status?: UserStatus;
  last_login_at?: string | null;
}

export interface SessionResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
  refresh_token?: string;
}

export interface TwoFactorChallengeResponse {
  two_factor_required: true;
  challenge_token: string;
  debug_code?: string | null;
}

export interface RegisterResponse {
  user: User;
  verification_required: boolean;
  verification_token?: string | null;
}

export interface ActionMessageResponse {
  message: string;
  action_token?: string | null;
}

export interface Preferences {
  theme: ThemePreference;
  language: Language;
  email_notifications: boolean;
  system_notifications: boolean;
}

export interface LinkItem {
  shortcode: string;
  url: string;
  short_url: string;
  label?: string | null;
  folder_id?: string | null;
  folder_name?: string | null;
  is_active: boolean;
  access_count: number;
  created_at: string;
  updated_at: string;
  last_accessed_at?: string | null;
}

export interface LinkListResponse {
  items: LinkItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateLinkPayload {
  url: string;
  mode: LinkMode;
  label?: string;
  folder_id?: string;
}

export interface CreateLinkResponse {
  shortcode: string;
  short_url: string;
  created: boolean;
  owner_id?: number | null;
  label?: string | null;
}

export interface UpdateLinkPayload {
  label?: string | null;
  folder_id?: string | null;
  is_active?: boolean;
}

export interface Folder {
  id: string;
  name: string;
  color: string;
  links_count: number;
  created_at: string;
}

export interface FolderListResponse {
  items: Folder[];
}

export interface AnalyticsMetric {
  key: string;
  label: string;
  value: number;
  change?: number | null;
}

export interface AnalyticsPoint {
  label: string;
  visits: number;
}

export interface AnalyticsResponse {
  metrics: AnalyticsMetric[];
  chart: AnalyticsPoint[];
  top_links: Array<Pick<LinkItem, "shortcode" | "label" | "access_count">>;
}

export interface ProfileResponse {
  user: User;
  preferences: Preferences;
  two_factor_enabled: boolean;
}

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  created_at: string;
  is_read: boolean;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  unread_count: number;
}

export interface ExportResponse {
  exported_at: string;
  data: Record<string, unknown>;
}
